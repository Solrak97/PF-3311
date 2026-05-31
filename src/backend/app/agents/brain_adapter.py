from __future__ import annotations

from typing import Any


async def complete_chat(brain: Any, messages: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    async for chunk in brain.stream_chat(messages):
        parts.append(chunk)
    return "".join(parts).strip()
