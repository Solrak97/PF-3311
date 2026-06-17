import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.brain.http_client import llm_timeout
from app.config import settings


class OpenAICompatBrain:
    """OpenAI-compatible chat completions API with streaming (Ollama, OpenAI, many gateways)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base = (base_url or settings.llm_base_url).rstrip("/")
        self._model = model or settings.resolved_llm_model
        self._api_key = api_key if api_key is not None else settings.llm_api_key

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        url = f"{self._base}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key.strip():
            headers["Authorization"] = f"Bearer {self._api_key.strip()}"
        body = {"model": self._model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=llm_timeout()) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload = line.removeprefix("data:").strip()
                    if payload == "[DONE]":
                        break
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    chunk = delta.get("content") or ""
                    if chunk:
                        yield chunk
