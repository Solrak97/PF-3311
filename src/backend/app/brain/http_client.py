from __future__ import annotations

import httpx

from app.config import settings


def llm_timeout() -> httpx.Timeout:
    """Generous read timeout for local 14B models; connect stays short."""
    total = float(settings.llm_timeout_sec)
    return httpx.Timeout(connect=15.0, read=total, write=30.0, pool=15.0)
