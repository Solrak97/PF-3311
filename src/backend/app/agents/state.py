from __future__ import annotations

from typing import Any, TypedDict


class InterviewAgentState(TypedDict, total=False):
    profile_id: str
    modeled_user_alias: str
    prompt_index: int
    total_prompts: int
    samples: list[dict[str, Any]]
    conversation_history: list[dict[str, Any]]
    skip: bool
    user_message: str
    system: str
    steering: str
    llm_messages: list[dict[str, str]]
    assistant_message: str
    complete: bool
    sample_saved: bool
    message: str


class ChatAgentState(TypedDict, total=False):
    condition: str
    profile_id: str
    user_message: str
    conversation_history: list[dict[str, Any]]
    session_turns: list[dict[str, Any]]
    include_ws_animation_protocol: bool
    system_prompt: str
    profile_used: bool
    retrieval_used: bool
    llm_messages: list[dict[str, Any]]
    assistant_message: str
