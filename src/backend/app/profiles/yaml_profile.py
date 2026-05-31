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
        "constraints": dict(DEFAULT_CONSTRAINTS),
    }


def parse_profile_yaml(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:yaml)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    data = yaml.safe_load(cleaned)
    if not isinstance(data, dict):
        raise ValueError("invalid_profile_yaml")
    return data


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
    profile = merge_constraints(profile)
    style = profile.get("style") or {}
    lexical = profile.get("lexical_patterns") or {}
    habits = profile.get("conversation_habits") or {}
    memory = profile.get("contextual_memory") or {}
    parts: list[str] = [
        "Responde en español siguiendo este perfil conductual.",
        f"Formalidad: {style.get('formality', 'medium')}. "
        f"Tono: {style.get('emotional_tone', 'conversacional')}. "
        f"Humor: {style.get('humor_style', 'ligero')}. "
        f"Longitud típica: {style.get('average_response_length', 'medium')}.",
    ]
    phrases = lexical.get("common_phrases") or []
    if isinstance(phrases, list) and phrases:
        parts.append("Frases frecuentes: " + ", ".join(str(p) for p in phrases[:8]))
    fillers = lexical.get("filler_words") or []
    if isinstance(fillers, list) and fillers:
        parts.append("Muletillas: " + ", ".join(str(p) for p in fillers[:8]))
    facts = memory.get("facts") or []
    if isinstance(facts, list) and facts:
        parts.append("Hechos contextuales seguros: " + "; ".join(str(f) for f in facts[:6]))
    parts.append(
        "No reveles que imitas a una persona concreta ni menciones el origen del perfil."
    )
    parts.append("Hábitos: " + ", ".join(f"{k}={v}" for k, v in habits.items()))
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
