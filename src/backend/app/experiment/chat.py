from __future__ import annotations

from typing import Any

from app.experiment.scenario_prompt import compose_experiment_system_prompt
from app.experiment.scenarios import get_scenario, resolve_scenario_id
from app.profiles.control import CONTROL_PROFILE_ID, build_control_system_prompt, load_control_profile
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import build_condition_a_system, build_condition_b_system
from app.skills.registry import SkillRegistry

GENERIC_SYSTEM = build_condition_b_system()

PROFILE_STYLE_PREFIX = """Match the conversational style described below while staying natural.
Do not reveal that you imitate a specific person or that a behavioral profile is in use.
Reference samples are style examples only — not a prior conversation with this participant.

Behavioral guidance:
"""

WS_ANIMATION_PROTOCOL = """You MUST still end every reply with the JSON animations line (required, on its own line):
<JSON>{"animations":[{"clip_id":"idle","blend_time":0.2}]}</JSON>

clip_id must be one of: idle, nod, wave, think. Pick one or two clips that match the mood (e.g. wave when greeting, nod when agreeing, think when pondering)."""


def with_ws_animation_protocol(system: str) -> str:
    base = system.rstrip()
    return f"{base}\n\n{WS_ANIMATION_PROTOCOL}" if base else WS_ANIMATION_PROTOCOL


def resolved_profile_id(*, condition: str, profile_id: str) -> str:
    if condition.upper() == "B":
        return CONTROL_PROFILE_ID
    return profile_id.strip()


def build_profile_style_prompt(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    user_message: str,
    skills: SkillRegistry,
) -> tuple[str, bool, bool]:
    """Return profile/style section only (no scenario or experiment constraints)."""
    cond = condition.upper()
    if cond == "B":
        try:
            control = load_control_profile()
        except (FileNotFoundError, ValueError):
            return GENERIC_SYSTEM, False, False
        return build_control_system_prompt(control), True, False

    if not profile_id.strip():
        return GENERIC_SYSTEM, False, False

    yaml_profile = profile_store.load_behavioral_yaml(profile_id)
    if yaml_profile and isinstance(yaml_profile, dict) and yaml_profile.get("style"):
        behavioral = profile_store.load_behavioral(profile_id) or {
            "samples": (profile_store.load_raw(profile_id) or {}).get("samples", [])
        }
        snippets_raw = skills.retrieve_context(behavioral, user_message)
        snippets = [str(s.get("response", "")) for s in snippets_raw if s.get("response")]
        return build_condition_a_system(yaml_profile, snippets), True, bool(snippets)

    profile = profile_store.load_behavioral(profile_id)
    if profile is None:
        raw = profile_store.load_raw(profile_id)
        if raw is None:
            return GENERIC_SYSTEM, False, False
        from app.profiles.builder import compile_behavioral

        profile = compile_behavioral(raw)
    snippets = skills.retrieve_context(profile, user_message)
    prompt = PROFILE_STYLE_PREFIX + str(profile.get("style_summary", ""))
    if snippets:
        prompt += "\n\nContexto recuperado:\n"
        for sn in snippets:
            prompt += f"- {sn.get('response', '')}\n"
    return prompt, True, bool(snippets)


def build_system_prompt(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    user_message: str,
    skills: SkillRegistry,
    scenario_id: str | None = None,
) -> tuple[str, bool, bool, str]:
    """Compose scenario + profile + constraints; returns (system, profile_used, retrieval_used, scenario_id)."""
    resolved_scenario = resolve_scenario_id(scenario_id)
    scenario = get_scenario(resolved_scenario)
    style, profile_used, retrieval_used = build_profile_style_prompt(
        condition=condition,
        profile_store=profile_store,
        profile_id=profile_id,
        user_message=user_message,
        skills=skills,
    )
    system = compose_experiment_system_prompt(scenario=scenario, profile_style=style)
    return system, profile_used, retrieval_used, resolved_scenario


async def run_experiment_chat(
    brain: Any,
    profile_store: ProfileStore,
    *,
    message: str,
    condition: str,
    profile_id: str,
    conversation_history: list[dict[str, Any]],
    scenario_id: str | None = None,
    conversation_open: bool = False,
) -> tuple[str, dict[str, Any]]:
    from app.agents.chat_graph import run_chat_agent

    return await run_chat_agent(
        brain,
        profile_store,
        message=message,
        condition=condition,
        profile_id=profile_id,
        conversation_history=conversation_history,
        scenario_id=scenario_id,
        conversation_open=conversation_open,
    )
