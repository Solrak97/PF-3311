from __future__ import annotations

from typing import Any

from app.profiles.control import CONTROL_PROFILE_ID, build_control_system_prompt, load_control_profile
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import build_condition_a_system, build_condition_b_system
from app.skills.registry import SkillRegistry

GENERIC_SYSTEM = build_condition_b_system()

PROFILE_SYSTEM_PREFIX = """You are Buddy, a friendly embodied assistant in a 3D scene.
Match the conversational style described below while staying natural. Do not reveal that you imitate a specific person.
Never use roleplay formatting: no *actions* or [directions]. Write only spoken words.

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


def build_system_prompt(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    user_message: str,
    skills: SkillRegistry,
) -> tuple[str, bool, bool]:
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
        behavioral = profile_store.load_behavioral(profile_id) or {"samples": (profile_store.load_raw(profile_id) or {}).get("samples", [])}
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
    prompt = PROFILE_SYSTEM_PREFIX + str(profile.get("style_summary", ""))
    if snippets:
        prompt += "\n\nContexto recuperado:\n"
        for sn in snippets:
            prompt += f"- {sn.get('response', '')}\n"
    return prompt, True, bool(snippets)


async def run_experiment_chat(
    brain: Any,
    profile_store: ProfileStore,
    *,
    message: str,
    condition: str,
    profile_id: str,
    conversation_history: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    from app.agents.chat_graph import run_chat_agent

    return await run_chat_agent(
        brain,
        profile_store,
        message=message,
        condition=condition,
        profile_id=profile_id,
        conversation_history=conversation_history,
    )
