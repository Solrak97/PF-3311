from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compile_behavioral(raw: dict[str, Any]) -> dict[str, Any]:
    samples = raw.get("samples") or []
    if not isinstance(samples, list):
        samples = []
    excerpts: list[str] = []
    for item in samples[:6]:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", "")).strip()
        response = str(item.get("response", "")).strip()
        if response:
            excerpts.append(f"P: {prompt}\nR: {response}")
    style = (
        "Responde de forma conversacional en español, con el tono y ritmo sugeridos por "
        "las muestras del perfil. No reveles identidad explícita ni digas que imitas a alguien. "
        "Las muestras son solo referencia de estilo; no actúes como si esa charla ya hubiera "
        "ocurrido con el participante actual."
    )
    if excerpts:
        style += "\n\nMuestras de referencia:\n" + "\n\n".join(excerpts)
    transcript = raw.get("interview_transcript") or []
    if isinstance(transcript, list) and len(transcript) > len(samples):
        style += "\n\n(La entrevista completa se guardó en interview_transcript.)"
    targets = raw.get("post_processing_targets") or []
    if isinstance(targets, list) and targets:
        style += "\n\nDimensiones a reflejar: " + ", ".join(str(t) for t in targets)
    return {
        "profile_id": raw.get("profile_id", ""),
        "modeled_user_alias": raw.get("modeled_user_alias", ""),
        "compiled_at": _utc_now_iso(),
        "style_summary": style,
        "samples": samples,
    }
