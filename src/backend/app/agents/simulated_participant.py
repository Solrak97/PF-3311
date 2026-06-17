from __future__ import annotations

import re
from typing import Any

from app.agents.brain_adapter import complete_chat
from app.agents.memory import build_llm_messages
from app.prompts.renderer import render_template
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader

SIMULATED_PARTICIPANT_SKILL_ID = "simulated_participant"


def _style_samples_from_raw(raw: dict[str, Any] | None, *, limit: int = 12) -> list[str]:
    if not raw:
        return []
    samples = raw.get("samples") or []
    if not isinstance(samples, list):
        return []
    lines: list[str] = []
    for item in samples:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", ""))
        if category == "mirror_calibration":
            continue
        response = str(item.get("response", "")).strip()
        if response and response not in {"[skipped]"}:
            lines.append(response)
    return lines[:limit]


def _phase_for_turn(turn_index: int, total_turns: int) -> str:
    if turn_index <= 2:
        return "opening"
    if turn_index >= total_turns - 1:
        return "closing"
    return "middle"


def _strip_participant_reply(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^(Participant|Participante|Usuario|User)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'")
    return cleaned.strip()


async def generate_participant_reply(
    brain: Any,
    *,
    buddy_last_message: str,
    conversation_history: list[dict[str, str]],
    profile_store: ProfileStore,
    profile_id: str,
    turn_index: int,
    total_turns: int,
    skills: SkillLoader | None = None,
) -> str:
    registry = skills or SkillLoader()
    skill = registry.get(SIMULATED_PARTICIPANT_SKILL_ID)

    raw = profile_store.load_raw(profile_id) or {}
    alias = str(raw.get("modeled_user_alias") or "Participante")
    style_samples = _style_samples_from_raw(raw)
    if not style_samples:
        style_samples = [
            "Pues hoy estuvo tranquilo, trabajé un rato y ya.",
            "Después suelo poner música y descansar un rato en el sillón.",
            "Últimamente me ha gustado mucho cocinar cosas sencillas.",
        ]

    system = render_template(
        skill.templates.get("system", "simulated_participant_system"),
        alias=alias,
        style_samples=style_samples,
    )
    user_prompt = render_template(
        skill.templates.get("turn", "simulated_participant_turn"),
        history=conversation_history,
        buddy_last=buddy_last_message.strip(),
        phase=_phase_for_turn(turn_index, total_turns),
    )
    messages = build_llm_messages(
        system_prompt=system,
        prior_messages=[],
        user_message=user_prompt,
        max_turns=4,
    )
    reply = await complete_chat(brain, messages)
    return _strip_participant_reply(reply)


async def generate_opening_participant_reply(
    brain: Any,
    *,
    buddy_opening: str,
    profile_store: ProfileStore,
    profile_id: str,
    total_turns: int,
    skills: SkillLoader | None = None,
) -> str:
    return await generate_participant_reply(
        brain,
        buddy_last_message=buddy_opening,
        conversation_history=[],
        profile_store=profile_store,
        profile_id=profile_id,
        turn_index=1,
        total_turns=total_turns,
        skills=skills,
    )
