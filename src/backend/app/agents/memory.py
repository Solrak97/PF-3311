from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

from app.pipeline.text_clean import strip_roleplay_markers


class MessageState(TypedDict, total=False):
    """LangGraph state with append-only message history."""

    messages: Annotated[list[AnyMessage], add_messages]


def dict_message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content.strip()}


def to_lc_messages(messages: list[dict[str, Any]]) -> list[AnyMessage]:
    out: list[AnyMessage] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=strip_roleplay_markers(content)))
    return out


def from_lc_messages(messages: list[AnyMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for message in messages:
        role = _lc_role(message)
        content = str(getattr(message, "content", "")).strip()
        if role and content:
            out.append(dict_message(role, content))
    return out


def _lc_role(message: AnyMessage) -> str:
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    message_type = str(getattr(message, "type", "")).lower()
    if message_type in {"system", "user", "assistant"}:
        return message_type
    return ""


def session_turns_to_messages(turns: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in turns:
        if not isinstance(item, dict):
            continue
        user_text = str(item.get("user_text", "")).strip()
        assistant_text = str(item.get("assistant_text", "")).strip()
        if user_text:
            messages.append(dict_message("user", user_text))
        if assistant_text:
            messages.append(dict_message("assistant", assistant_text))
    return messages


def history_to_messages(history: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append(dict_message(role, content))
    return messages


def trim_message_dicts(
    messages: list[dict[str, str]],
    *,
    max_turns: int,
) -> list[dict[str, str]]:
    """Keep the system prompt and the most recent user/assistant turns."""
    if not messages:
        return []
    system_msgs = [m for m in messages if m["role"] == "system"]
    dialog = [m for m in messages if m["role"] in {"user", "assistant"}]
    if max_turns > 0:
        dialog = dialog[-max_turns:]
    return [*system_msgs, *dialog]


def build_llm_messages(
    *,
    system_prompt: str,
    prior_messages: list[dict[str, str]],
    user_message: str = "",
    conversation_open_cue: str = "",
    max_turns: int = 12,
) -> list[dict[str, str]]:
    messages = [dict_message("system", system_prompt), *prior_messages]
    if user_message.strip():
        messages.append(dict_message("user", user_message.strip()))
    elif conversation_open_cue.strip():
        messages.append(dict_message("user", conversation_open_cue.strip()))
    return trim_message_dicts(messages, max_turns=max_turns + 1)
