from __future__ import annotations

import httpx

from app.config import settings


def llm_timeout(*, read_sec: float | None = None) -> httpx.Timeout:
    """Generous read timeout for local models; connect stays short."""
    total = float(read_sec if read_sec is not None else settings.llm_timeout_sec)
    connect = 8.0 if settings.llm_fallback_base_url.strip() else 15.0
    return httpx.Timeout(connect=connect, read=total, write=30.0, pool=connect)


def llm_fallback_timeout() -> httpx.Timeout:
    read = float(settings.llm_fallback_timeout_sec)
    return httpx.Timeout(connect=8.0, read=read, write=30.0, pool=8.0)
