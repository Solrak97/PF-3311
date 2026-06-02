"""Short-lived MP3 cache for HTTP delivery (avoids huge WebSocket JSON frames)."""

from __future__ import annotations

import secrets
import threading
from typing import Final

_MAX_ENTRIES: Final[int] = 128
_lock = threading.Lock()
_cache: dict[str, bytes] = {}


def store_turn_audio(session_id: str, turn_index: int, segment_index: int, mp3: bytes) -> str:
    """Store MP3 bytes and return URL path for GET /audio/turn/{token}."""
    _ = (session_id, turn_index, segment_index)  # reserved for logging / future namespacing
    token = secrets.token_urlsafe(16)
    with _lock:
        if len(_cache) >= _MAX_ENTRIES:
            oldest = next(iter(_cache))
            del _cache[oldest]
        _cache[token] = mp3
    return f"/audio/turn/{token}"


def pop_turn_audio(token: str) -> bytes | None:
    with _lock:
        return _cache.pop(token, None)
