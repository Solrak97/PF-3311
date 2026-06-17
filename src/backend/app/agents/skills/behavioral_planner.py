from __future__ import annotations

import json
import re
from typing import Any

from app.agents.brain_adapter import complete_chat
from app.config import settings
from app.experiment.scenarios import get_scenario
from app.profiles.yaml_profile import profile_to_style_summary
from app.prompts.renderer import render_template

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _default_plan(situation: str) -> dict[str, Any]:
    return {
        "response_strategy": ["acknowledge", "respond naturally", "optional follow-up"],
        "tone": "conversational",
        "structure": ["short opener", "main point", "optional question"],
        "behaviors": ["avoid meta labels", "use tú", "stay concise"],
        "goals": [f"handle {situation} naturally"],
    }


def _parse_plan(raw: str) -> dict[str, Any]:
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
        raise ValueError("invalid_plan_json")
    return {
        "response_strategy": _as_list(data.get("response_strategy")),
        "tone": str(data.get("tone", "conversational")).strip(),
        "structure": _as_list(data.get("structure")),
        "behaviors": _as_list(data.get("behaviors")),
        "goals": _as_list(data.get("goals")),
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def build_heuristic_plan(yaml_profile: dict[str, Any], situation: str) -> dict[str, Any]:
    """Build a behavioral plan from YAML situation_modes without an LLM call."""
    plan = _default_plan(situation)
    modes = yaml_profile.get("situation_modes") if isinstance(yaml_profile, dict) else {}
    situation_mode = modes.get(situation) if isinstance(modes, dict) else None
    if isinstance(situation_mode, dict):
        traits = situation_mode.get("traits") or []
        strategies = situation_mode.get("response_strategy") or []
        if traits:
            plan["behaviors"] = [str(t) for t in traits[:4]]
        if strategies:
            plan["response_strategy"] = [str(s) for s in strategies[:3]]
    response_structure = yaml_profile.get("response_structure") or {}
    default_pattern = response_structure.get("default_pattern")
    if isinstance(default_pattern, list) and default_pattern:
        plan["structure"] = [str(x) for x in default_pattern[:4]]
    habits = yaml_profile.get("conversation_habits") or {}
    if isinstance(habits, dict):
        habit_notes = [f"{k}: {v}" for k, v in habits.items() if v][:3]
        if habit_notes:
            plan["goals"] = habit_notes + plan["goals"]
    style = yaml_profile.get("style") or {}
    if isinstance(style, dict) and style.get("formality"):
        plan["tone"] = str(style.get("formality", "conversational"))
    return plan


async def plan_behavioral_response(
    brain: Any,
    *,
    yaml_profile: dict[str, Any],
    user_message: str,
    situation: str,
    retrieved_moments: list[dict[str, Any]] | None = None,
    scenario_id: str | None = None,
    avoid_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Skill 5: pre-generation behavioral plan."""
    mode = (settings.behavioral_planner_mode or "auto").strip().lower()
    if mode in {"heuristic", "auto"} and not avoid_notes:
        return build_heuristic_plan(yaml_profile, situation)

    scenario = get_scenario(scenario_id)
    modes = yaml_profile.get("situation_modes") if isinstance(yaml_profile, dict) else {}
    situation_mode = modes.get(situation) if isinstance(modes, dict) else None
    prompt = render_template(
        "behavioral_plan",
        profile_summary=profile_to_style_summary(yaml_profile),
        situation=situation,
        situation_mode=situation_mode,
        retrieved_moments=retrieved_moments or [],
        scenario=scenario,
        user_message=user_message.strip(),
    )
    if avoid_notes:
        prompt += "\n\nAvoid in this regeneration:\n" + "\n".join(f"- {n}" for n in avoid_notes)
    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await complete_chat(brain, messages, num_predict=settings.llm_num_predict_json)
        return _parse_plan(raw)
    except (json.JSONDecodeError, ValueError):
        plan = build_heuristic_plan(yaml_profile, situation)
        if isinstance(situation_mode, dict):
            traits = situation_mode.get("traits") or []
            strategies = situation_mode.get("response_strategy") or []
            if traits:
                plan["behaviors"] = [str(t) for t in traits[:4]] + plan["behaviors"]
            if strategies:
                plan["response_strategy"] = [str(s) for s in strategies[:3]]
        return plan
    except Exception:  # noqa: BLE001
        return build_heuristic_plan(yaml_profile, situation)
