from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Brain(Protocol):
    """Streams assistant text deltas (incremental chunks)."""

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        ...
