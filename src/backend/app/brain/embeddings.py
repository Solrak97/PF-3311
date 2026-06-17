from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx

from app.brain.http_client import llm_timeout
from app.config import settings

logger = logging.getLogger(__name__)

_EMBED_CACHE: dict[str, list[float]] = {}
_EMBED_CACHE_MAX = 512
_EMBED_WARNED = False


@lru_cache(maxsize=1)
def _ollama_model_names() -> frozenset[str]:
    url = f"{settings.llm_base_url.rstrip('/')}/api/tags"
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:  # noqa: BLE001
        return frozenset()
    names: set[str] = set()
    for item in data.get("models") or []:
        if isinstance(item, dict) and item.get("name"):
            names.add(str(item["name"]))
            base = str(item["name"]).split(":")[0]
            names.add(base)
    return frozenset(names)


def embed_model_available(model: str | None = None) -> bool:
    if not settings.embeddings_enabled:
        return False
    embed_model = model or settings.ollama_embed_model
    tags = _ollama_model_names()
    if not tags:
        return True
    if embed_model in tags:
        return True
    return embed_model.split(":")[0] in tags


async def embed_text(text: str, *, model: str | None = None) -> list[float] | None:
    """Embed text via Ollama /api/embeddings. Returns None if unavailable."""
    global _EMBED_WARNED

    if not settings.embeddings_enabled:
        return None

    prompt = text.strip()
    if not prompt:
        return None

    embed_model = model or settings.ollama_embed_model
    cache_key = f"{embed_model}:{prompt[:500]}"
    cached = _EMBED_CACHE.get(cache_key)
    if cached is not None:
        return cached

    if not embed_model_available(embed_model):
        if not _EMBED_WARNED:
            logger.warning(
                "embedding_model_missing model=%s (run: ollama pull %s)",
                embed_model,
                embed_model,
            )
            _EMBED_WARNED = True
        return None

    url = f"{settings.llm_base_url.rstrip('/')}/api/embeddings"
    body = {"model": embed_model, "prompt": prompt}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45.0)) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        if not _EMBED_WARNED:
            logger.warning("embedding_unavailable model=%s err=%s", embed_model, exc)
            _EMBED_WARNED = True
        return None

    embedding = data.get("embedding")
    if isinstance(embedding, list) and embedding:
        vector = [float(x) for x in embedding]
        if len(_EMBED_CACHE) >= _EMBED_CACHE_MAX:
            _EMBED_CACHE.pop(next(iter(_EMBED_CACHE)))
        _EMBED_CACHE[cache_key] = vector
        return vector
    return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
