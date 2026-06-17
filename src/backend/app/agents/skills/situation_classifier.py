from __future__ import annotations

import json
import re
from typing import Any

from app.agents.brain_adapter import complete_chat
from app.agents.skills.behavioral_observer import SITUATION_TAXONOMY
from app.config import settings
from app.prompts.renderer import render_template

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_KEYWORD_MAP: dict[str, tuple[str, ...]] = {
    "emotional_reaction": ("triste", "enojad", "feliz", "preocup", "ansiedad", "miedo", "siento"),
    "banter_advice": ("consejo", "debería", "qué harías", "opinas", "recomiend"),
    "comforting": ("ánimo", "mal día", "difícil", "apoyo", "consuelo"),
    "brainstorming": ("idea", "plan", "opciones", "alternativa", "brainstorm"),
    "teaching": ("explica", "cómo funciona", "qué es", "enseña", "tutorial"),
    "routine_register": ("día", "trabajo", "rutina", "mañana", "tarde", "cena"),
    "discourse": ("opinas", "piensas", "debate", "discutir", "argument"),
}


def _keyword_classify(user_message: str) -> tuple[str, float]:
    text = user_message.lower()
    best_situation = "open"
    best_score = 0
    for situation, keywords in _KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_situation = situation
    confidence = min(0.9, 0.3 + best_score * 0.15) if best_score else 0.2
    return best_situation, confidence


def _parse_classification(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    situation = str(data.get("situation", "open")).strip().lower()
    if situation not in SITUATION_TAXONOMY:
        situation = "open"
    try:
        confidence = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    return {"situation": situation, "confidence": max(0.0, min(1.0, confidence))}


async def classify_situation(
    brain: Any,
    *,
    user_message: str,
    recent_context: str = "",
    use_llm: bool | None = None,
) -> dict[str, Any]:
    """Skill 3: classify current interaction situation."""
    if not user_message.strip():
        return {"situation": "open", "confidence": 0.0, "method": "empty"}

    keyword_situation, keyword_conf = _keyword_classify(user_message)
    mode = (settings.situation_classifier_mode or "auto").strip().lower()

    if mode == "keyword":
        return {"situation": keyword_situation, "confidence": keyword_conf, "method": "keyword"}

    llm_enabled = use_llm if use_llm is not None else mode in {"auto", "llm"}
    if mode == "auto" and keyword_conf >= 0.35:
        return {"situation": keyword_situation, "confidence": keyword_conf, "method": "keyword_auto"}

    if not llm_enabled or not brain:
        return {"situation": keyword_situation, "confidence": keyword_conf, "method": "keyword"}

    prompt = render_template(
        "situation_classifier",
        user_message=user_message.strip(),
        recent_context=recent_context[:400] or "(none)",
        situation_taxonomy=", ".join(SITUATION_TAXONOMY),
    )
    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await complete_chat(brain, messages, num_predict=settings.llm_num_predict_json)
        parsed = _parse_classification(raw)
        return {**parsed, "method": "llm"}
    except (json.JSONDecodeError, ValueError):
        return {"situation": keyword_situation, "confidence": keyword_conf, "method": "keyword_fallback"}
    except Exception:  # noqa: BLE001
        return {"situation": keyword_situation, "confidence": keyword_conf, "method": "keyword_error_fallback"}
