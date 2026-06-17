from __future__ import annotations

import re
from typing import Any

import yaml

DEFAULT_CONSTRAINTS = {
    "do_not_claim_to_be_person": True,
    "do_not_reveal_profile_source": True,
    "keep_identity_ambiguous": True,
    "avoid_visual_identity_references": True,
    "avoid_sensitive_personal_data": True,
}


def default_profile_template(profile_id: str, source: str = "training") -> dict[str, Any]:
    return {
        "profile_id": profile_id,
        "profile_version": "1.0.0",
        "source": source,
        "style": {
            "formality": "medium",
            "pronouns": "tú",
            "average_response_length": "medium",
            "emotional_tone": "conversacional",
            "humor_style": "ligero",
        },
        "lexical_patterns": {
            "common_phrases": [],
            "filler_words": [],
            "avoided_phrases": [],
        },
        "voice_exemplars": [],
        "conversation_habits": {
            "asks_follow_up_questions": "medium",
            "validates_user_feelings": "medium",
            "uses_short_reactions": "medium",
            "gives_examples": "medium",
            "tells_anecdotes": "low",
        },
        "response_structure": {"default_pattern": ["acknowledge", "respond", "optional_follow_up"]},
        "contextual_memory": {
            "allowed_topics": [],
            "facts": [],
            "reference_style": "subtle",
        },
        "situation_modes": {},
        "constraints": dict(DEFAULT_CONSTRAINTS),
    }


def _as_dict(value: Any, *, list_key: str = "tags") -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return {list_key: [str(item) for item in value]}
    if value is None:
        return {}
    return {"value": str(value)}


def normalize_profile_yaml(profile: dict[str, Any]) -> dict[str, Any]:
    """Coerce LLM-extracted YAML into the expected behavioral profile shape."""
    base = default_profile_template(str(profile.get("profile_id", "")))
    merged = dict(base)
    merged.update(profile)
    merged["style"] = {**base["style"], **_as_dict(profile.get("style"), list_key="traits")}
    lexical = _as_dict(profile.get("lexical_patterns"), list_key="patterns")
    merged["lexical_patterns"] = {
        **base["lexical_patterns"],
        **lexical,
        "common_phrases": lexical.get("common_phrases")
        or lexical.get("patterns")
        or base["lexical_patterns"]["common_phrases"],
    }
    merged["conversation_habits"] = {
        **base["conversation_habits"],
        **_as_dict(profile.get("conversation_habits"), list_key="habits"),
    }
    exemplars = profile.get("voice_exemplars")
    if isinstance(exemplars, list):
        merged["voice_exemplars"] = [
            item for item in exemplars if isinstance(item, dict) and item.get("line")
        ]
    elif isinstance(exemplars, dict):
        merged["voice_exemplars"] = [exemplars]
    else:
        merged["voice_exemplars"] = base.get("voice_exemplars", [])
    response_structure = profile.get("response_structure")
    if isinstance(response_structure, dict):
        merged["response_structure"] = response_structure
    elif isinstance(response_structure, list):
        merged["response_structure"] = {"default_pattern": [str(item) for item in response_structure]}
    memory = profile.get("contextual_memory")
    if isinstance(memory, dict):
        merged["contextual_memory"] = {**base["contextual_memory"], **memory}
    else:
        merged["contextual_memory"] = {
            **base["contextual_memory"],
            "reference_style": str(memory) if memory is not None else "subtle",
        }
    modes = profile.get("situation_modes")
    if isinstance(modes, dict):
        normalized_modes: dict[str, Any] = {}
        for key, value in modes.items():
            if not isinstance(value, dict):
                continue
            traits = value.get("traits") or []
            strategies = value.get("response_strategy") or []
            normalized_modes[str(key)] = {
                "traits": [str(t).strip() for t in traits if str(t).strip()],
                "response_strategy": [str(s).strip() for s in strategies if str(s).strip()],
            }
        merged["situation_modes"] = normalized_modes
    else:
        merged["situation_modes"] = {}
    return merge_constraints(merged)


def _looks_like_serialized_dict(text: str) -> bool:
    stripped = text.strip()
    return (
        stripped.startswith("{")
        and stripped.endswith("}")
        and (":" in stripped or "'" in stripped)
    )


def sanitize_grounded_phrases(profile: dict[str, Any]) -> dict[str, Any]:
    """Reject corrupted LLM output in lexical_patterns (e.g. nested dict strings)."""
    out = dict(profile)
    lexical = out.get("lexical_patterns")
    if not isinstance(lexical, dict):
        return out
    cleaned_lexical = dict(lexical)
    for key in ("common_phrases", "filler_words", "avoided_phrases"):
        raw = lexical.get(key)
        if not isinstance(raw, list):
            continue
        cleaned: list[str] = []
        for item in raw:
            if isinstance(item, dict):
                line = str(item.get("line") or item.get("text") or "").strip()
                if line and not _looks_like_serialized_dict(line):
                    cleaned.append(line)
                continue
            text = str(item).strip()
            if not text or _looks_like_serialized_dict(text):
                continue
            if len(text) > 120 and text.count(":") >= 2:
                continue
            cleaned.append(text)
        cleaned_lexical[key] = cleaned
    out["lexical_patterns"] = cleaned_lexical
    exemplars = out.get("voice_exemplars")
    if isinstance(exemplars, list):
        out["voice_exemplars"] = [
            ex
            for ex in exemplars
            if isinstance(ex, dict)
            and str(ex.get("line", "")).strip()
            and not _looks_like_serialized_dict(str(ex.get("line", "")))
        ]
    return out


def parse_profile_yaml(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:yaml)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    data = yaml.safe_load(cleaned)
    if not isinstance(data, dict):
        raise ValueError("invalid_profile_yaml")
    return normalize_profile_yaml(data)


def dump_profile_yaml(profile: dict[str, Any]) -> str:
    return yaml.safe_dump(profile, allow_unicode=True, sort_keys=False)


def merge_constraints(profile: dict[str, Any]) -> dict[str, Any]:
    out = dict(profile)
    constraints = dict(DEFAULT_CONSTRAINTS)
    raw = profile.get("constraints")
    if isinstance(raw, dict):
        constraints.update(raw)
    out["constraints"] = constraints
    return out


def profile_to_style_summary(profile: dict[str, Any]) -> str:
    profile = normalize_profile_yaml(profile) if isinstance(profile, dict) else {}
    style = profile.get("style") if isinstance(profile.get("style"), dict) else {}
    lexical = profile.get("lexical_patterns") if isinstance(profile.get("lexical_patterns"), dict) else {}
    memory = profile.get("contextual_memory") if isinstance(profile.get("contextual_memory"), dict) else {}
    exemplars = profile.get("voice_exemplars") or []
    parts: list[str] = [
        "Responde en español con la voz del perfil. Demuestra el tono con palabras — no lo describas.",
        f"Formalidad: {style.get('formality', 'medium')}. "
        f"Longitud típica: {style.get('average_response_length', 'medium')}. "
        f"Pronombres: {style.get('pronouns', 'tú')}.",
    ]
    phrases = lexical.get("common_phrases") or []
    if isinstance(phrases, list) and phrases:
        parts.append("Frases frecuentes: " + ", ".join(str(p) for p in phrases[:10]))
    fillers = lexical.get("filler_words") or []
    if isinstance(fillers, list) and fillers:
        parts.append("Muletillas: " + ", ".join(str(p) for p in fillers[:8]))
    avoided = lexical.get("avoided_phrases") or []
    if isinstance(avoided, list) and avoided:
        parts.append("Evitar: " + ", ".join(str(p) for p in avoided[:6]))
    if isinstance(exemplars, list) and exemplars:
        lines = [
            f"- {str(ex.get('line', '')).strip()}"
            for ex in exemplars[:6]
            if isinstance(ex, dict) and str(ex.get("line", "")).strip()
        ]
        if lines:
            parts.append("Ejemplos de voz:\n" + "\n".join(lines))
    facts = memory.get("facts") or []
    if isinstance(facts, list) and facts:
        parts.append("Hechos contextuales seguros: " + "; ".join(str(f) for f in facts[:6]))
    parts.append(
        "No reveles que imitas a una persona concreta ni menciones el origen del perfil."
    )
    return "\n".join(parts)


def build_condition_a_system(profile: dict[str, Any], retrieval_snippets: list[str] | None = None) -> str:
    from app.agents.prompts import CONDITION_A_RESPONSE_PROMPT

    retrieval = "\n".join(f"- {s}" for s in (retrieval_snippets or [])) or "(none)"
    return CONDITION_A_RESPONSE_PROMPT.format(
        profile=dump_profile_yaml(merge_constraints(profile)),
        retrieval=retrieval,
    )


def build_condition_b_system() -> str:
    from app.agents.prompts import CONDITION_B_RESPONSE_PROMPT

    return CONDITION_B_RESPONSE_PROMPT
