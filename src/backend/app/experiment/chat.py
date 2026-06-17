from __future__ import annotations

from typing import Any

from app.agents.conversation_agent import (
    build_profile_style_prompt,
    build_system_prompt,
    prepare_chat_messages,
    resolved_profile_id,
    run_chat_agent,
)
from app.prompts.renderer import render_template
from app.skills.loader import SkillLoader

WS_ANIMATION_PROTOCOL = render_template("ws_animation_protocol")


def with_ws_animation_protocol(system: str) -> str:
    base = system.rstrip()
    return f"{base}\n\n{WS_ANIMATION_PROTOCOL}" if base else WS_ANIMATION_PROTOCOL


async def run_experiment_chat(
    brain: Any,
    profile_store: Any,
    *,
    message: str,
    condition: str,
    profile_id: str,
    conversation_history: list[dict[str, Any]],
    scenario_id: str | None = None,
    conversation_open: bool = False,
) -> tuple[str, dict[str, Any]]:
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


__all__ = [
    "WS_ANIMATION_PROTOCOL",
    "build_profile_style_prompt",
    "build_system_prompt",
    "prepare_chat_messages",
    "resolved_profile_id",
    "run_experiment_chat",
    "with_ws_animation_protocol",
]
