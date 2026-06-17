from __future__ import annotations

from typing import Any


async def complete_chat(
    brain: Any,
    messages: list[dict[str, Any]],
    *,
    num_predict: int | None = None,
) -> str:
    parts: list[str] = []
    kwargs = {}
    if num_predict is not None:
        kwargs["num_predict"] = num_predict
    async for chunk in brain.stream_chat(messages, **kwargs):
        parts.append(chunk)
    return "".join(parts).strip()
