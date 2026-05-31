from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.state import ChatAgentState
from app.experiment.chat import build_system_prompt, resolved_profile_id, with_ws_animation_protocol
from app.pipeline.text_clean import strip_roleplay_markers
from app.profiles.store import ProfileStore
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


def _resolve_profile_context(state: ChatAgentState) -> ChatAgentState:
    profile_store: ProfileStore = state["_profile_store"]
    skills: SkillRegistry = state["_skills"]
    condition = str(state.get("condition", "B"))
    profile_id = str(state.get("profile_id", ""))
    user_message = str(state.get("user_message", "")).strip()
    system, profile_used, retrieval_used = build_system_prompt(
        condition=condition,
        profile_store=profile_store,
        profile_id=profile_id,
        user_message=user_message,
        skills=skills,
    )
    if state.get("include_ws_animation_protocol"):
        system = with_ws_animation_protocol(system)
    return {
        **state,
        "system_prompt": system,
        "profile_used": profile_used,
        "retrieval_used": retrieval_used,
    }


def _assemble_llm_messages(state: ChatAgentState) -> ChatAgentState:
    system = str(state.get("system_prompt", ""))
    user_message = str(state.get("user_message", "")).strip()
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]

    session_turns = state.get("session_turns") or []
    if session_turns:
        for item in session_turns:
            if not isinstance(item, dict):
                continue
            prev_user = str(item.get("user_text", "")).strip()
            prev_assistant = str(item.get("assistant_text", "")).strip()
            if prev_user:
                messages.append({"role": "user", "content": prev_user})
            if prev_assistant:
                messages.append(
                    {
                        "role": "assistant",
                        "content": strip_roleplay_markers(prev_assistant),
                    }
                )
    else:
        for item in (state.get("conversation_history") or [])[-12:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", ""))
            content = str(item.get("content", "")).strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    if user_message:
        messages.append({"role": "user", "content": user_message})

    return {**state, "llm_messages": messages}


def _build_context_graph():
    graph = StateGraph(ChatAgentState)
    graph.add_node("resolve_profile_context", _resolve_profile_context)
    graph.add_node("assemble_llm_messages", _assemble_llm_messages)
    graph.add_edge(START, "resolve_profile_context")
    graph.add_edge("resolve_profile_context", "assemble_llm_messages")
    graph.add_edge("assemble_llm_messages", END)
    return graph.compile()


def _build_chat_graph(brain: Any):
    context_graph = _build_context_graph()
    full = StateGraph(ChatAgentState)

    async def run_context(state: ChatAgentState) -> ChatAgentState:
        return await context_graph.ainvoke(state)

    async def generate(state: ChatAgentState) -> ChatAgentState:
        llm_messages = state.get("llm_messages") or []
        assistant_message = await complete_chat(brain, llm_messages)
        logger.info(
            "chat_graph condition=%s profile=%s profile_used=%s retrieval=%s messages=%d",
            state.get("condition", ""),
            state.get("profile_id", ""),
            state.get("profile_used", False),
            state.get("retrieval_used", False),
            len(llm_messages),
        )
        return {**state, "assistant_message": assistant_message}

    full.add_node("context", run_context)
    full.add_node("generate", generate)
    full.add_edge(START, "context")
    full.add_edge("context", "generate")
    full.add_edge("generate", END)
    return full.compile()


async def prepare_chat_messages(
    profile_store: ProfileStore,
    *,
    condition: str,
    profile_id: str,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    session_turns: list[dict[str, Any]] | None = None,
    include_ws_animation_protocol: bool = False,
    skills: SkillRegistry | None = None,
) -> tuple[list[dict[str, Any]], bool, bool]:
    graph = _build_context_graph()
    result = await graph.ainvoke(
        {
            "_profile_store": profile_store,
            "_skills": skills or SkillRegistry(),
            "condition": condition,
            "profile_id": profile_id,
            "user_message": user_message,
            "conversation_history": conversation_history or [],
            "session_turns": session_turns or [],
            "include_ws_animation_protocol": include_ws_animation_protocol,
        }
    )
    return (
        list(result.get("llm_messages") or []),
        bool(result.get("profile_used", False)),
        bool(result.get("retrieval_used", False)),
    )


async def run_chat_agent(
    brain: Any,
    profile_store: ProfileStore,
    *,
    message: str,
    condition: str,
    profile_id: str,
    conversation_history: list[dict[str, Any]] | None = None,
    session_turns: list[dict[str, Any]] | None = None,
    include_ws_animation_protocol: bool = False,
    skills: SkillRegistry | None = None,
) -> tuple[str, dict[str, Any]]:
    graph = _build_chat_graph(brain)
    result = await graph.ainvoke(
        {
            "_profile_store": profile_store,
            "_skills": skills or SkillRegistry(),
            "condition": condition,
            "profile_id": profile_id,
            "user_message": message.strip(),
            "conversation_history": conversation_history or [],
            "session_turns": session_turns or [],
            "include_ws_animation_protocol": include_ws_animation_protocol,
        }
    )
    meta = {
        "condition": condition.upper(),
        "profile_id": resolved_profile_id(condition=condition, profile_id=profile_id),
        "profile_used": bool(result.get("profile_used", False)),
        "retrieval_used": bool(result.get("retrieval_used", False)),
        "control_profile": condition.upper() == "B",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return str(result.get("assistant_message", "")).strip(), meta
