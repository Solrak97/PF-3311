"""Check LLM, embeddings, and profile stack health."""

from __future__ import annotations

import asyncio
import json
import sys

import httpx

from app.brain.embeddings import embed_model_available, embed_text
from app.brain.factory import create_brain
from app.config import settings
from app.profiles.store import ProfileStore


async def _check_llm() -> dict:
    url = f"{settings.llm_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            tags = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}

    names = [m.get("name") for m in tags.get("models") or [] if isinstance(m, dict)]
    model = settings.resolved_llm_model
    model_ok = model in names or model.split(":")[0] in {n.split(":")[0] for n in names if n}
    return {
        "ok": model_ok,
        "provider": settings.llm_provider,
        "model": model,
        "installed_models": names,
        "model_installed": model_ok,
    }


async def _check_embed() -> dict:
    model = settings.ollama_embed_model
    available = embed_model_available(model)
    sample = None
    if available:
        sample = await embed_text("hola mundo")
    return {
        "ok": available and sample is not None,
        "model": model,
        "model_installed": available,
        "sample_dims": len(sample) if sample else 0,
        "enabled": settings.embeddings_enabled,
    }


async def _check_chat() -> dict:
    brain = create_brain()
    try:
        from app.agents.brain_adapter import complete_chat

        reply = await complete_chat(
            brain,
            [{"role": "user", "content": "Responde solo: OK"}],
            num_predict=8,
        )
        return {"ok": bool(reply.strip()), "sample": reply.strip()[:80]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _check_profiles() -> dict:
    store = ProfileStore(settings.profiles_data_dir)
    ids = store.list_profile_ids()
    return {"ok": bool(ids), "profile_ids": ids, "count": len(ids)}


async def main() -> int:
    llm = await _check_llm()
    embed = await _check_embed()
    chat = await _check_chat()
    profiles = _check_profiles()

    report = {
        "llm": llm,
        "embeddings": embed,
        "chat_smoke": chat,
        "profiles": profiles,
        "settings": {
            "timeout_sec": settings.llm_timeout_sec,
            "num_predict": settings.llm_num_predict,
            "classifier_mode": settings.situation_classifier_mode,
            "planner_mode": settings.behavioral_planner_mode,
        },
    }
    report["ok"] = all(
        [
            llm.get("ok"),
            chat.get("ok"),
            profiles.get("ok"),
        ]
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not embed.get("ok"):
        print(
            f"\nTip: ollama pull {settings.ollama_embed_model}",
            file=sys.stderr,
        )
    if not llm.get("model_installed"):
        print(
            f"\nTip: ollama pull {settings.resolved_llm_model}",
            file=sys.stderr,
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
