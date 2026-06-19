from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.memory import (
    build_llm_messages,
    history_to_messages,
    session_turns_to_messages,
)
from app.agents.skills.behavioral_planner import plan_behavioral_response
from app.agents.skills.example_retriever import retrieve_examples
from app.agents.skills.situation_classifier import classify_situation
from app.agents.state import ChatAgentState
from app.experiment.scenarios import get_scenario, resolve_scenario_id
from app.pipeline.text_clean import strip_roleplay_markers
from app.profiles.control import CONTROL_PROFILE_ID, build_control_system_prompt, load_control_profile
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import build_condition_b_system, dump_profile_yaml, merge_constraints
from app.prompts.renderer import render_template
from app.skills.loader import SkillLoader

logger = logging.getLogger(__name__)

CONVERSATION_SKILL_ID = "converse_with_profile"


def resolved_profile_id(*, condition: str, profile_id: str) -> str:
    if condition.upper() == "B":
        return CONTROL_PROFILE_ID
    return profile_id.strip()


def _generic_style() -> str:
    return build_condition_b_system()


def _ablation(state: ChatAgentState, key: str) -> bool:
    flags = state.get("ablation_flags") or {}
    if not isinstance(flags, dict):
        return False
    return bool(flags.get(key))


def _recent_context(state: ChatAgentState) -> str:
    turns = state.get("session_turns") or state.get("conversation_history") or []
    lines: list[str] = []
    for item in turns[-4:]:
        if not isinstance(item, dict):
            continue
        user = str(item.get("user_text") or item.get("content", "")).strip()
        assistant = str(item.get("assistant_text", "")).strip()
        if user:
            lines.append(f"user: {user[:120]}")
        if assistant:
            lines.append(f"assistant: {assistant[:120]}")
    return "\n".join(lines)


def build_profile_style_prompt(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    user_message: str,
    skills: SkillLoader,
    active_situation: str = "",
    retrieved_moments: list[dict[str, Any]] | None = None,
    behavioral_plan: dict[str, Any] | None = None,
    retrieval_snippets: list[str] | None = None,
) -> tuple[str, bool, bool]:
    cond = condition.upper()
    if cond == "B":
        try:
            control = load_control_profile()
        except (FileNotFoundError, ValueError):
            return _generic_style(), False, False
        control_prompt = build_control_system_prompt(control)
        style = render_template(
            "control_profile_block",
            control_prompt=control_prompt,
        )
        return style, True, False

    if not profile_id.strip():
        return _generic_style(), False, False

    yaml_profile = profile_store.load_behavioral_yaml(profile_id)
    if yaml_profile and isinstance(yaml_profile, dict) and yaml_profile.get("style"):
        profile_yaml = dump_profile_yaml(merge_constraints(yaml_profile))
        is_test_baseline = str(yaml_profile.get("kind", "")).strip() == "test_baseline"
        block_template = (
            "profile_block_test_baseline" if is_test_baseline else "profile_block"
        )
        moments = retrieved_moments or []
        snippets = retrieval_snippets or [
            str(m.get("exemplar_line", "")) for m in moments if m.get("exemplar_line")
        ]
        style = render_template(
            block_template,
            profile_yaml=profile_yaml,
            retrieval_snippets=snippets,
            active_situation=active_situation,
            retrieved_moments=moments,
            behavioral_plan=behavioral_plan or {},
        )
        return style, True, bool(moments or snippets)

    profile = profile_store.load_behavioral(profile_id)
    if profile is None:
        raw = profile_store.load_raw(profile_id)
        if raw is None:
            return _generic_style(), False, False
        from app.profiles.builder import compile_behavioral

        profile = compile_behavioral(raw)
    snippets_raw = skills.retrieve_context(CONVERSATION_SKILL_ID, profile, user_message)
    snippet_texts = [str(s.get("response", "")) for s in snippets_raw if s.get("response")]
    style = render_template(
        "legacy_profile_style",
        style_summary=str(profile.get("style_summary", "")),
        retrieval_snippets=snippet_texts,
    )
    return style, True, bool(snippet_texts)


def build_open_cue(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    skills: SkillLoader,
) -> str:
    skill = skills.get(CONVERSATION_SKILL_ID)
    if condition.upper() != "A" or not profile_id.strip():
        return render_template(skill.templates.get("open_cue", "conversation_open_cue"))
    yaml_profile = profile_store.load_behavioral_yaml(profile_id)
    if isinstance(yaml_profile, dict) and str(yaml_profile.get("kind", "")).strip() == "test_baseline":
        return render_template(
            skill.templates.get("open_cue_test_baseline", "conversation_open_test_baseline"),
        )
    return render_template(skill.templates.get("open_cue", "conversation_open_cue"))


def _is_test_baseline_profile(profile_store: ProfileStore, profile_id: str) -> bool:
    if not profile_id.strip():
        return False
    yaml_profile = profile_store.load_behavioral_yaml(profile_id)
    return isinstance(yaml_profile, dict) and str(yaml_profile.get("kind", "")).strip() == "test_baseline"


def build_system_prompt(
    *,
    condition: str,
    profile_store: ProfileStore,
    profile_id: str,
    user_message: str,
    skills: SkillLoader,
    scenario_id: str | None = None,
    include_ws_animation_protocol: bool = False,
    active_situation: str = "",
    retrieved_moments: list[dict[str, Any]] | None = None,
    behavioral_plan: dict[str, Any] | None = None,
) -> tuple[str, bool, bool, str]:
    resolved_scenario = resolve_scenario_id(scenario_id)
    scenario = get_scenario(resolved_scenario)
    profile_style, profile_used, retrieval_used = build_profile_style_prompt(
        condition=condition,
        profile_store=profile_store,
        profile_id=profile_id,
        user_message=user_message,
        skills=skills,
        active_situation=active_situation,
        retrieved_moments=retrieved_moments,
        behavioral_plan=behavioral_plan,
    )
    skill = skills.get(CONVERSATION_SKILL_ID)
    ws_protocol = ""
    if include_ws_animation_protocol:
        ws_protocol = render_template(skill.templates.get("ws_animation", "ws_animation_protocol"))
    is_test_baseline = (
        condition.upper() == "A"
        and _is_test_baseline_profile(profile_store, profile_id)
    )
    system = render_template(
        skill.templates.get("system", "conversation_system"),
        scenario=scenario,
        profile_style=profile_style,
        condition=condition.upper(),
        is_test_baseline=is_test_baseline,
        ws_animation_protocol=ws_protocol,
        behavioral_plan=behavioral_plan or {},
    )
    return system, profile_used, retrieval_used, resolved_scenario


def _make_classify_situation(brain: Any):
    async def _classify(state: ChatAgentState) -> ChatAgentState:
        if state.get("condition", "B").upper() != "A" or _ablation(state, "no_situation"):
            return {**state, "active_situation": "open", "situation_confidence": 0.0}
        classified = await classify_situation(
            brain,
            user_message=str(state.get("user_message", "")),
            recent_context=_recent_context(state),
        )
        return {
            **state,
            "active_situation": classified.get("situation", "open"),
            "situation_confidence": float(classified.get("confidence", 0.0)),
        }

    return _classify


def _make_retrieve_moments(profile_store: ProfileStore, skills: SkillLoader):
    async def _retrieve(state: ChatAgentState) -> ChatAgentState:
        if state.get("condition", "B").upper() != "A" or _ablation(state, "no_retrieval"):
            return {**state, "retrieved_moments": [], "retrieval_used": False, "moment_ids": []}
        profile_id = str(state.get("profile_id", ""))
        yaml_profile = profile_store.load_behavioral_yaml(profile_id)
        moments, used = await retrieve_examples(
            profile_store,
            profile_id,
            user_message=str(state.get("user_message", "")),
            situation=str(state.get("active_situation", "open")),
            yaml_profile=yaml_profile,
            skills=skills,
        )
        moment_ids = [str(m.get("id", "")) for m in moments if m.get("id")]
        return {
            **state,
            "retrieved_moments": moments,
            "retrieval_used": used,
            "moment_ids": moment_ids,
        }

    return _retrieve


def _make_plan_behavior(brain: Any, profile_store: ProfileStore):
    async def _plan(state: ChatAgentState) -> ChatAgentState:
        if state.get("condition", "B").upper() != "A" or _ablation(state, "no_planner"):
            return {**state, "behavioral_plan": {}}
        profile_id = str(state.get("profile_id", ""))
        yaml_profile = profile_store.load_behavioral_yaml(profile_id)
        if not isinstance(yaml_profile, dict):
            return {**state, "behavioral_plan": {}}
        if _ablation(state, "no_situation_modes"):
            yaml_profile = dict(yaml_profile)
            yaml_profile.pop("situation_modes", None)
        plan = await plan_behavioral_response(
            brain,
            yaml_profile=yaml_profile,
            user_message=str(state.get("user_message", "")),
            situation=str(state.get("active_situation", "open")),
            retrieved_moments=state.get("retrieved_moments") or [],
            scenario_id=str(state.get("scenario_id", "")) or None,
        )
        return {**state, "behavioral_plan": plan}

    return _plan


def _make_resolve_context(profile_store: ProfileStore, skills: SkillLoader):
    def _resolve_context(state: ChatAgentState) -> ChatAgentState:
        if _ablation(state, "l1_replay"):
            profile_id = str(state.get("profile_id", ""))
            raw = profile_store.load_raw(profile_id) or {}
            samples = raw.get("samples") or []
            snippets = [
                str(s.get("response", ""))
                for s in samples[:3]
                if isinstance(s, dict) and s.get("response")
            ]
            system, profile_used, retrieval_used, resolved_scenario = build_system_prompt(
                condition=str(state.get("condition", "B")),
                profile_store=profile_store,
                profile_id=profile_id,
                user_message=str(state.get("user_message", "")).strip(),
                skills=skills,
                scenario_id=str(state.get("scenario_id", "")) or None,
                include_ws_animation_protocol=bool(state.get("include_ws_animation_protocol")),
            )
            profile_style, _, _ = build_profile_style_prompt(
                condition="A",
                profile_store=profile_store,
                profile_id=profile_id,
                user_message=str(state.get("user_message", "")),
                skills=skills,
                retrieval_snippets=snippets,
            )
            skill = skills.get(CONVERSATION_SKILL_ID)
            scenario = get_scenario(resolved_scenario)
            system = render_template(
                skill.templates.get("system", "conversation_system"),
                scenario=scenario,
                profile_style=profile_style,
                condition="A",
                is_test_baseline=False,
                ws_animation_protocol="",
                behavioral_plan={},
            )
            return {
                **state,
                "system_prompt": system,
                "profile_used": profile_used,
                "retrieval_used": bool(snippets),
                "scenario_id": resolved_scenario,
            }

        system, profile_used, retrieval_used, resolved_scenario = build_system_prompt(
            condition=str(state.get("condition", "B")),
            profile_store=profile_store,
            profile_id=str(state.get("profile_id", "")),
            user_message=str(state.get("user_message", "")).strip(),
            skills=skills,
            scenario_id=str(state.get("scenario_id", "")) or None,
            include_ws_animation_protocol=bool(state.get("include_ws_animation_protocol")),
            active_situation=str(state.get("active_situation", "")),
            retrieved_moments=state.get("retrieved_moments") or [],
            behavioral_plan=state.get("behavioral_plan") or {},
        )
        return {
            **state,
            "system_prompt": system,
            "profile_used": profile_used,
            "retrieval_used": bool(state.get("retrieval_used")) or retrieval_used,
            "scenario_id": resolved_scenario,
        }

    return _resolve_context


def _make_assemble_messages(profile_store: ProfileStore, skills: SkillLoader):
    def _assemble_messages(state: ChatAgentState) -> ChatAgentState:
        skill = skills.get(CONVERSATION_SKILL_ID)
        memory = skill.memory
        max_ws = int(memory.get("max_turns_ws", 8))
        max_http = int(memory.get("max_turns_http", 12))

        prior: list[dict[str, str]] = []
        session_turns = state.get("session_turns") or []
        if session_turns:
            prior = session_turns_to_messages(session_turns)
            max_turns = max_ws * 2
        else:
            prior = history_to_messages(state.get("conversation_history") or [])
            max_turns = max_http * 2

        open_cue = ""
        if state.get("conversation_open"):
            open_cue = build_open_cue(
                condition=str(state.get("condition", "B")),
                profile_store=profile_store,
                profile_id=str(state.get("profile_id", "")),
                skills=skills,
            )

        messages = build_llm_messages(
            system_prompt=str(state.get("system_prompt", "")),
            prior_messages=prior,
            user_message=str(state.get("user_message", "")).strip(),
            conversation_open_cue=open_cue,
            max_turns=max_turns,
        )
        return {**state, "llm_messages": messages}

    return _assemble_messages


def _build_pre_context_graph(brain: Any, profile_store: ProfileStore, skills: SkillLoader):
    graph = StateGraph(ChatAgentState)
    graph.add_node("classify_situation", _make_classify_situation(brain))
    graph.add_node("retrieve_moments", _make_retrieve_moments(profile_store, skills))
    graph.add_node("plan_behavior", _make_plan_behavior(brain, profile_store))
    graph.add_edge(START, "classify_situation")
    graph.add_edge("classify_situation", "retrieve_moments")
    graph.add_edge("retrieve_moments", "plan_behavior")
    graph.add_edge("plan_behavior", END)
    return graph.compile()


def _build_context_graph(brain: Any, profile_store: ProfileStore, skills: SkillLoader):
    pre_graph = _build_pre_context_graph(brain, profile_store, skills)
    graph = StateGraph(ChatAgentState)

    async def run_pre(state: ChatAgentState) -> ChatAgentState:
        return await pre_graph.ainvoke(state)

    graph.add_node("pre_context", run_pre)
    graph.add_node("resolve_context", _make_resolve_context(profile_store, skills))

    def assemble(state: ChatAgentState) -> ChatAgentState:
        return _make_assemble_messages(profile_store, skills)(state)

    graph.add_node("assemble_messages", assemble)
    graph.add_edge(START, "pre_context")
    graph.add_edge("pre_context", "resolve_context")
    graph.add_edge("resolve_context", "assemble_messages")
    graph.add_edge("assemble_messages", END)
    return graph.compile()


def _build_conversation_graph(brain: Any, profile_store: ProfileStore, skills: SkillLoader):
    context_graph = _build_context_graph(brain, profile_store, skills)
    graph = StateGraph(ChatAgentState)

    async def run_context(state: ChatAgentState) -> ChatAgentState:
        return await context_graph.ainvoke(state)

    async def generate(state: ChatAgentState) -> ChatAgentState:
        llm_messages = state.get("llm_messages") or []
        assistant_message = await complete_chat(brain, llm_messages)
        result: ChatAgentState = {
            **state,
            "assistant_message": strip_roleplay_markers(assistant_message),
            "regen_attempted": False,
        }
        if (
            state.get("condition", "B").upper() == "A"
            and not _ablation(state, "no_evaluator")
        ):
            from app.agents.skills.familiarity_evaluator import (
                evaluate_familiarity,
                runtime_regen_enabled,
                should_regenerate,
            )

            if runtime_regen_enabled():
                profile_id = str(state.get("profile_id", ""))
                yaml_profile = profile_store.load_behavioral_yaml(profile_id)
                if isinstance(yaml_profile, dict):
                    eval_result = await evaluate_familiarity(
                        brain,
                        profile=yaml_profile,
                        prompt=str(state.get("user_message", "")),
                        agent_response=assistant_message,
                        plan=state.get("behavioral_plan")
                        if isinstance(state.get("behavioral_plan"), dict)
                        else None,
                    )
                    result["familiarity_score"] = eval_result.get("plan_match_score")
                    if should_regenerate(eval_result):
                        avoid = [str(eval_result.get("rationale", "low familiarity score"))]
                        plan = await plan_behavioral_response(
                            brain,
                            yaml_profile=yaml_profile,
                            user_message=str(state.get("user_message", "")),
                            situation=str(state.get("active_situation", "open")),
                            retrieved_moments=state.get("retrieved_moments") or [],
                            scenario_id=str(state.get("scenario_id", "")) or None,
                            avoid_notes=avoid,
                        )
                        regen_state = {
                            **state,
                            "behavioral_plan": plan,
                        }
                        regen_state = _make_resolve_context(profile_store, skills)(regen_state)
                        regen_state = _make_assemble_messages(profile_store, skills)(regen_state)
                        regen_messages = regen_state.get("llm_messages") or []
                        regen_reply = await complete_chat(brain, regen_messages)
                        result = {
                            **regen_state,
                            "assistant_message": strip_roleplay_markers(regen_reply),
                            "regen_attempted": True,
                        }
        logger.info(
            "conversation_agent condition=%s profile=%s scenario=%s situation=%s retrieval=%s plan=%s regen=%s",
            state.get("condition", ""),
            state.get("profile_id", ""),
            state.get("scenario_id", ""),
            state.get("active_situation", ""),
            state.get("retrieval_used", False),
            bool(state.get("behavioral_plan")),
            result.get("regen_attempted", False),
        )
        return result

    graph.add_node("context", run_context)
    graph.add_node("generate", generate)
    graph.add_edge(START, "context")
    graph.add_edge("context", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _invoke_state(
    *,
    condition: str,
    profile_id: str,
    scenario_id: str | None,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None,
    session_turns: list[dict[str, Any]] | None,
    include_ws_animation_protocol: bool,
    conversation_open: bool = False,
    ablation_flags: dict[str, bool] | None = None,
) -> ChatAgentState:
    return {
        "condition": condition,
        "profile_id": profile_id,
        "scenario_id": scenario_id or "",
        "conversation_open": conversation_open,
        "user_message": user_message,
        "conversation_history": conversation_history or [],
        "session_turns": session_turns or [],
        "include_ws_animation_protocol": include_ws_animation_protocol,
        "ablation_flags": ablation_flags or {},
        "active_situation": "",
        "retrieved_moments": [],
        "moment_ids": [],
        "behavioral_plan": {},
    }


async def prepare_chat_messages(
    profile_store: ProfileStore,
    *,
    condition: str,
    profile_id: str,
    user_message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    session_turns: list[dict[str, Any]] | None = None,
    include_ws_animation_protocol: bool = False,
    skills: SkillLoader | None = None,
    scenario_id: str | None = None,
    conversation_open: bool = False,
    brain: Any | None = None,
    ablation_flags: dict[str, bool] | None = None,
) -> tuple[list[dict[str, Any]], bool, bool, str, dict[str, Any]]:
    registry = skills or SkillLoader()
    if brain is None:
        from app.brain.factory import create_brain

        brain = create_brain()
    graph = _build_context_graph(brain, profile_store, registry)
    result = await graph.ainvoke(
        _invoke_state(
            condition=condition,
            profile_id=profile_id,
            scenario_id=scenario_id,
            user_message=user_message,
            conversation_history=conversation_history,
            session_turns=session_turns,
            include_ws_animation_protocol=include_ws_animation_protocol,
            conversation_open=conversation_open,
            ablation_flags=ablation_flags,
        )
    )
    instrumentation = {
        "active_situation": str(result.get("active_situation", "")),
        "situation_confidence": float(result.get("situation_confidence", 0.0)),
        "retrieval_used": bool(result.get("retrieval_used", False)),
        "moment_ids": list(result.get("moment_ids") or []),
        "has_behavioral_plan": bool(result.get("behavioral_plan")),
    }
    return (
        list(result.get("llm_messages") or []),
        bool(result.get("profile_used", False)),
        bool(result.get("retrieval_used", False)),
        str(result.get("scenario_id", "")),
        instrumentation,
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
    skills: SkillLoader | None = None,
    scenario_id: str | None = None,
    conversation_open: bool = False,
    ablation_flags: dict[str, bool] | None = None,
) -> tuple[str, dict[str, Any]]:
    registry = skills or SkillLoader()
    graph = _build_conversation_graph(brain, profile_store, registry)
    result = await graph.ainvoke(
        _invoke_state(
            condition=condition,
            profile_id=profile_id,
            scenario_id=scenario_id,
            user_message=message.strip(),
            conversation_history=conversation_history,
            session_turns=session_turns,
            include_ws_animation_protocol=include_ws_animation_protocol,
            conversation_open=conversation_open,
            ablation_flags=ablation_flags,
        )
    )
    meta = {
        "condition": condition.upper(),
        "profile_id": resolved_profile_id(condition=condition, profile_id=profile_id),
        "scenario_id": str(result.get("scenario_id", "")),
        "conversation_open": conversation_open,
        "profile_used": bool(result.get("profile_used", False)),
        "retrieval_used": bool(result.get("retrieval_used", False)),
        "active_situation": str(result.get("active_situation", "")),
        "situation_confidence": float(result.get("situation_confidence", 0.0)),
        "moment_ids": list(result.get("moment_ids") or []),
        "has_behavioral_plan": bool(result.get("behavioral_plan")),
        "regen_attempted": bool(result.get("regen_attempted", False)),
        "familiarity_score": result.get("familiarity_score"),
        "control_profile": condition.upper() == "B",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return str(result.get("assistant_message", "")).strip(), meta
