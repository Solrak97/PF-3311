from __future__ import annotations

import json
import re
from typing import Any

from app.agents.brain_adapter import complete_chat
from app.prompts.renderer import render_template
from app.skills.loader import SkillLoader

TRAINING_SKILL_ID = "train_profile"

SITUATION_TAXONOMY = (
    "routine_register",
    "emotional_reaction",
    "banter_advice",
    "discourse",
    "comforting",
    "brainstorming",
    "teaching",
    "open",
    "mirror_calibration",
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _parse_observation_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("invalid_observation_json")
    situation = str(data.get("situation_hint", "open")).strip().lower()
    if situation not in SITUATION_TAXONOMY:
        situation = "open"
    return {
        "reasoning_style": _as_str_list(data.get("reasoning_style")),
        "emotional_patterns": _as_str_list(data.get("emotional_patterns")),
        "conversational_habits": _as_str_list(data.get("conversational_habits")),
        "recurring_structures": _as_str_list(data.get("recurring_structures")),
        "situation_hint": situation,
    }


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _transcript_slice(transcript: list[dict[str, Any]], *, max_lines: int = 6) -> str:
    lines: list[str] = []
    for item in transcript[-max_lines:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role and content and content != "[skipped]":
            lines.append(f"{role}: {content[:200]}")
    return "\n".join(lines) or "(empty)"


async def observe_exchange(
    brain: Any,
    *,
    prompt: str,
    response: str,
    category: str,
    transcript: list[dict[str, Any]] | None = None,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    """Skill 1: extract abstract behavioral observations from one exchange."""
    if not response.strip() or response.strip() == "[skipped]":
        return {
            "reasoning_style": [],
            "emotional_patterns": [],
            "conversational_habits": [],
            "recurring_structures": [],
            "situation_hint": category or "open",
            "skipped": True,
        }
    user_prompt = render_template(
        "training_behavioral_observation",
        prompt=prompt.strip(),
        response=response.strip(),
        category=category or "open",
        situation_taxonomy=", ".join(SITUATION_TAXONOMY),
        transcript_slice=_transcript_slice(transcript or []),
    )
    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": user_prompt},
    ]
    raw = await complete_chat(brain, messages)
    try:
        observation = _parse_observation_json(raw)
    except (json.JSONDecodeError, ValueError):
        observation = {
            "reasoning_style": [],
            "emotional_patterns": [],
            "conversational_habits": [],
            "recurring_structures": [],
            "situation_hint": category or "open",
            "parse_failed": True,
        }
    observation["category"] = category or "open"
    observation["prompt"] = prompt.strip()
    return observation


def merge_observation_into_situation_modes(
    profile: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Merge one observation into profile.situation_modes."""
    situation = str(observation.get("situation_hint") or observation.get("category") or "open")
    modes = profile.get("situation_modes")
    if not isinstance(modes, dict):
        modes = {}
    entry = modes.get(situation)
    if not isinstance(entry, dict):
        entry = {"traits": [], "response_strategy": []}
    traits = list(entry.get("traits") or [])
    strategies = list(entry.get("response_strategy") or [])
    for key in ("reasoning_style", "emotional_patterns", "conversational_habits", "recurring_structures"):
        for item in observation.get(key) or []:
            text = str(item).strip()
            if text and text not in traits:
                traits.append(text)
    modes[situation] = {
        "traits": traits[:12],
        "response_strategy": strategies[:8],
    }
    profile["situation_modes"] = modes
    return profile
