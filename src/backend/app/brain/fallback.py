from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.brain.http_client import llm_fallback_timeout
from app.brain.ollama import OllamaBrain
from app.config import settings

logger = logging.getLogger(__name__)


class FallbackOllamaBrain:
    """Try primary Ollama first; on failure use fallback (with cooldown after fallback errors)."""

    def __init__(
        self,
        *,
        primary_url: str | None = None,
        primary_model: str | None = None,
        fallback_url: str | None = None,
        fallback_model: str | None = None,
    ) -> None:
        self._primary = OllamaBrain(base_url=primary_url, model=primary_model)
        fb_url = (fallback_url or settings.llm_fallback_base_url).strip().rstrip("/")
        self._fallback: OllamaBrain | None = None
        if fb_url:
            fb_model = (fallback_model or settings.resolved_llm_fallback_model or "").strip()
            self._fallback = OllamaBrain(
                base_url=fb_url,
                model=fb_model or settings.resolved_llm_model,
                timeout=llm_fallback_timeout(),
            )
        self._fallback_cooldown_until = 0.0
        self._last_endpoint: str | None = None

    @property
    def last_endpoint(self) -> str | None:
        return self._last_endpoint

    def _fallback_in_cooldown(self) -> bool:
        return time.monotonic() < self._fallback_cooldown_until

    def _note_fallback_failure(self) -> None:
        self._fallback_cooldown_until = time.monotonic() + float(settings.llm_fallback_cooldown_sec)
        logger.warning(
            "ollama_fallback_cooldown sec=%s until retry",
            settings.llm_fallback_cooldown_sec,
        )

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        if isinstance(exc, (TimeoutError, httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout)):
            return True
        if isinstance(exc, httpx.HTTPError):
            return True
        return False

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        *,
        num_predict: int | None = None,
    ) -> AsyncIterator[str]:
        errors: list[tuple[str, BaseException]] = []
        kwargs: dict[str, Any] = {}
        if num_predict is not None:
            kwargs["num_predict"] = num_predict

        try:
            async for chunk in self._primary.stream_chat(messages, **kwargs):
                self._last_endpoint = self._primary._base  # noqa: SLF001
                yield chunk
            return
        except Exception as exc:  # noqa: BLE001
            if not self._is_retryable(exc):
                raise
            errors.append((self._primary._base, exc))  # noqa: SLF001
            logger.warning("ollama_primary_failed base=%s err=%s", self._primary._base, exc)

        if self._fallback is None:
            raise errors[-1][1]

        if self._fallback_in_cooldown():
            primary_exc = errors[-1][1]
            raise TimeoutError(
                f"Primary Ollama failed ({self._primary._base}); "  # noqa: SLF001
                f"fallback {self._fallback._base} in cooldown"  # noqa: SLF001
            ) from primary_exc

        logger.info("ollama_trying_fallback base=%s model=%s", self._fallback._base, self._fallback._model)
        try:
            async for chunk in self._fallback.stream_chat(messages, **kwargs):
                self._last_endpoint = self._fallback._base  # noqa: SLF001
                yield chunk
        except Exception as exc:  # noqa: BLE001
            self._note_fallback_failure()
            if errors:
                raise TimeoutError(
                    f"Primary ({errors[-1][0]}) and fallback ({self._fallback._base}) Ollama failed"
                ) from exc
            raise
