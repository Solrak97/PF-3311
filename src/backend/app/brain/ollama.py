import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings


class OllamaBrain:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self._base = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        url = f"{self._base}/api/chat"
        body = {"model": self._model, "messages": messages, "stream": True}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
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
