from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.state import InterviewAgentState
from app.experiment.interview import (
    INTERVIEW_SYSTEM_PROMPT,
    _load_interview_skill,
    _progress_block,
    _prompt_items,
    _safety_block,
    _utc_now_iso,
    build_interview_messages,
    last_assistant_before_last_user,
    normalize_history,
)
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


def _prepare_start(state: InterviewAgentState) -> InterviewAgentState:
    skill = _load_interview_skill()
    prompts = _prompt_items(skill)
    if not prompts:
        raise ValueError("interview_skill_missing_prompts")
    first = prompts[0]
    system = INTERVIEW_SYSTEM_PROMPT + _safety_block(skill) + _progress_block(
        answered_index=0,
        total=len(prompts),
        next_prompt=first,
    )
    alias = str(state.get("modeled_user_alias", "")).strip()
    profile_id = str(state.get("profile_id", "")).strip()
    alias_note = f"Participant alias: {alias}." if alias else ""
    steering = (
        f"[START_INTERVIEW profile_id={profile_id}. {alias_note}]\n"
        "Welcome the participant briefly in a warm, natural tone. "
        "Remind them they may skip any question. "
        "Then ask your first question inspired by the next topic (do not read it verbatim)."
    )
    return {
        **state,
        "prompt_index": 0,
        "total_prompts": len(prompts),
        "samples": [],
        "conversation_history": [],
        "complete": False,
        "sample_saved": False,
        "system": system,
        "steering": steering,
    }


def _prepare_turn(state: InterviewAgentState) -> InterviewAgentState:
    skill = _load_interview_skill()
    prompts = _prompt_items(skill)
    if not prompts:
        raise ValueError("interview_skill_missing_prompts")

    prompt_index = int(state.get("prompt_index", 0))
    if prompt_index < 0 or prompt_index >= len(prompts):
        raise ValueError("invalid_prompt_index")

    history = state.get("conversation_history") or []
    current = prompts[prompt_index]
    updated_samples = list(state.get("samples") or [])
    skip = bool(state.get("skip", False))
    user_message = str(state.get("user_message", "")).strip()
    sample_saved = False
    asked_prompt = last_assistant_before_last_user(history) or str(current.get("text", ""))

    if not skip and user_message:
        updated_samples.append(
            {
                "prompt_id": str(current.get("id", "")),
                "category": str(current.get("category", "")),
                "prompt": asked_prompt,
                "response": user_message,
                "timestamp": _utc_now_iso(),
            }
        )
        sample_saved = True

    next_index = prompt_index + 1
    complete = next_index >= len(prompts)
    nxt = prompts[next_index] if not complete else None
    system = INTERVIEW_SYSTEM_PROMPT + _safety_block(skill) + _progress_block(
        answered_index=next_index,
        total=len(prompts),
        next_prompt=nxt,
    )

    if complete:
        steering = (
            "[INTERVIEW_COMPLETE] Based on the full conversation above, thank the participant briefly. "
            "Tell them they can press Save to store the profile. Do not ask another question."
        )
    elif skip:
        steering = (
            f"[INTERVIEWER_TURN {next_index + 1}/{len(prompts)}] "
            "The participant skipped the previous question. Acknowledge briefly without pressure. "
            "Then ask ONE new question inspired by the next topic (do not quote it verbatim)."
        )
    else:
        steering = (
            f"[INTERVIEWER_TURN {next_index + 1}/{len(prompts)}] "
            "Read the participant's last answer in the conversation above. "
            "Give a brief natural acknowledgment, then ask ONE follow-up question inspired by the next topic "
            "(do not quote it verbatim)."
        )

    return {
        **state,
        "samples": updated_samples,
        "sample_saved": sample_saved,
        "prompt_index": next_index,
        "total_prompts": len(prompts),
        "complete": complete,
        "system": system,
        "steering": steering,
    }


def _build_messages(state: InterviewAgentState) -> InterviewAgentState:
    system = str(state.get("system", ""))
    steering = str(state.get("steering", ""))
    history = state.get("conversation_history") or []
    llm_messages = build_interview_messages(
        system=system,
        conversation_history=history,
        steering=steering,
    )
    return {**state, "llm_messages": llm_messages}


async def _generate(state: InterviewAgentState, *, brain: Any) -> InterviewAgentState:
    llm_messages = state.get("llm_messages") or []
    assistant_message = await complete_chat(brain, llm_messages)
    logger.info(
        "interview_graph profile=%s index=%s history=%d complete=%s",
        state.get("profile_id", ""),
        state.get("prompt_index", 0),
        len(normalize_history(state.get("conversation_history") or [])),
        state.get("complete", False),
    )
    return {
        **state,
        "assistant_message": assistant_message,
        "message": assistant_message,
    }


def _build_start_graph(brain: Any):
    graph = StateGraph(InterviewAgentState)
    graph.add_node("prepare_start", _prepare_start)
    graph.add_node("build_messages", _build_messages)

    async def generate_node(state: InterviewAgentState) -> InterviewAgentState:
        return await _generate(state, brain=brain)

    graph.add_node("generate", generate_node)
    graph.add_edge(START, "prepare_start")
    graph.add_edge("prepare_start", "build_messages")
    graph.add_edge("build_messages", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _build_turn_graph(brain: Any):
    graph = StateGraph(InterviewAgentState)
    graph.add_node("prepare_turn", _prepare_turn)
    graph.add_node("build_messages", _build_messages)

    async def generate_node(state: InterviewAgentState) -> InterviewAgentState:
        return await _generate(state, brain=brain)

    graph.add_node("generate", generate_node)
    graph.add_edge(START, "prepare_turn")
    graph.add_edge("prepare_turn", "build_messages")
    graph.add_edge("build_messages", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


async def run_interview_start(
    brain: Any,
    *,
    profile_id: str,
    modeled_user_alias: str,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    if registry is not None:
        _load_interview_skill(registry)
    graph = _build_start_graph(brain)
    result = await graph.ainvoke(
        {
            "profile_id": profile_id,
            "modeled_user_alias": modeled_user_alias,
        }
    )
    return {
        "message": result.get("message", ""),
        "prompt_index": int(result.get("prompt_index", 0)),
        "total_prompts": int(result.get("total_prompts", 0)),
        "complete": bool(result.get("complete", False)),
        "samples": list(result.get("samples") or []),
    }


async def run_interview_turn(
    brain: Any,
    *,
    profile_id: str,
    modeled_user_alias: str,
    prompt_index: int,
    user_message: str,
    samples: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]] | None = None,
    skip: bool = False,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    if registry is not None:
        _load_interview_skill(registry)
    graph = _build_turn_graph(brain)
    result = await graph.ainvoke(
        {
            "profile_id": profile_id,
            "modeled_user_alias": modeled_user_alias,
            "prompt_index": prompt_index,
            "user_message": user_message,
            "samples": samples,
            "conversation_history": conversation_history or [],
            "skip": skip,
        }
    )
    return {
        "message": result.get("message", ""),
        "prompt_index": int(result.get("prompt_index", prompt_index)),
        "total_prompts": int(result.get("total_prompts", 0)),
        "complete": bool(result.get("complete", False)),
        "samples": list(result.get("samples") or samples),
        "sample_saved": bool(result.get("sample_saved", False)),
    }
