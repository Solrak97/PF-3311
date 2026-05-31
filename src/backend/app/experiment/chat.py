from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.profiles.control import CONTROL_PROFILE_ID, build_control_system_prompt, load_control_profile
from app.profiles.store import ProfileStore
from app.skills.registry import SkillRegistry

GENERIC_SYSTEM = """You are Buddy, a friendly embodied assistant in a 3D scene.
Keep answers concise and conversational (this will be spoken aloud). Prefer short paragraphs in Spanish when the user writes in Spanish.
Use only the conversation history in this chat. Do not claim to remember other sessions.
Never use roleplay formatting: no *actions* or [directions]. Write only spoken words."""

PROFILE_SYSTEM_PREFIX = """You are Buddy, a friendly embodied assistant in a 3D scene.
Match the conversational style described below while staying natural. Do not reveal that you imitate a specific person.
Never use roleplay formatting: no *actions* or [directions]. Write only spoken words.

Behavioral guidance:
"""

WS_ANIMATION_PROTOCOL = """You MUST still end every reply with the JSON animations line (required, on its own line):
<JSON>{"animations":[{"clip_id":"idle","blend_time":0.2}]}</JSON>

clip_id must be one of: idle, nod, wave, think. Pick one or two clips that match the mood (e.g. wave when greeting, nod when agreeing, think when pondering)."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    profile = profile_store.load_behavioral(profile_id)
    if profile is None:
        return GENERIC_SYSTEM, False, False
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
    skills = SkillRegistry()
    system, profile_used, retrieval_used = build_system_prompt(
        condition=condition,
        profile_store=profile_store,
        profile_id=profile_id,
        user_message=message,
        skills=skills,
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for item in conversation_history[-12:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", ""))
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})
    parts: list[str] = []
    async for chunk in brain.stream_chat(messages):
        parts.append(chunk)
    text = "".join(parts).strip()
    meta = {
        "condition": condition.upper(),
        "profile_id": resolved_profile_id(condition=condition, profile_id=profile_id),
        "profile_used": profile_used,
        "retrieval_used": retrieval_used,
        "control_profile": condition.upper() == "B",
        "timestamp": _utc_now_iso(),
    }
    return text, meta
