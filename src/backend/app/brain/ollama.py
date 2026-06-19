import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.brain.http_client import llm_timeout
from app.config import settings

logger = logging.getLogger(__name__)


class OllamaBrain:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._base = (base_url or settings.llm_base_url).rstrip("/")
        self._model = model or settings.resolved_llm_model
        self._timeout = timeout

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        num_predict: int | None = None,
    ) -> AsyncIterator[str]:
        url = f"{self._base}/api/chat"
        predict = num_predict if num_predict is not None else settings.llm_num_predict
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "keep_alive": settings.ollama_keep_alive,
            "think": settings.ollama_think,
            "options": {
                "num_predict": max(32, int(predict)),
                "temperature": 0.7,
            },
        }
        try:
            timeout = self._timeout or llm_timeout()
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=body) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if data.get("done"):
                            break
                        msg = data.get("message") or {}
                        chunk = msg.get("content") or ""
                        if chunk:
                            yield chunk
        except httpx.ReadTimeout as exc:
            logger.error(
                "ollama_read_timeout model=%s timeout_sec=%s",
                self._model,
                settings.llm_timeout_sec,
            )
            raise TimeoutError(
                f"Ollama read timeout after {settings.llm_timeout_sec}s "
                f"(model={self._model}). Try a smaller model or increase LLM_TIMEOUT_SEC."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("ollama_http_error model=%s err=%s", self._model, exc)
            raise
