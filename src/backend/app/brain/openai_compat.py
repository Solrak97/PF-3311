from collections.abc import AsyncIterator
from typing import Any


class OpenAICompatBrain:
    """Placeholder for a future OpenAI-compatible HTTP streaming client."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        raise NotImplementedError("Wire OpenAI-compatible streaming here when upgrading from Ollama.")
