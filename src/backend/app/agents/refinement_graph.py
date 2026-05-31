from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.prompts import PROFILE_REFINEMENT_PROMPT
from app.experiment.chat import run_experiment_chat
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import parse_profile_yaml, profile_to_style_summary

RATING_KEYS = (
    "tone_similarity",
    "phrasing_similarity",
    "response_length_similarity",
    "behavioral_consistency",
    "reminds_me_of_person",
    "naturalness",
    "identity_leakage_absent",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_behavioral_profile(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile_id = str(state.get("profile_id", ""))
    profile = store.load_behavioral_yaml(profile_id) or store.load_final_profile(profile_id)
    if profile is None:
        raise ValueError("profile_not_found")
    return {**state, "behavioral_profile": profile, "status": "refinement"}


async def generate_profile_based_response(
    brain: Any,
    store: ProfileStore,
    state: BehavioralProfileState,
    *,
    user_message: str,
) -> BehavioralProfileState:
    history = list(state.get("refinement_transcript") or [])
    text, _meta = await run_experiment_chat(
        brain,
        store,
        message=user_message,
        condition="A",
        profile_id=str(state.get("profile_id", "")),
        conversation_history=history,
    )
    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": text})
    return {
        **state,
        "message": text,
        "refinement_transcript": history,
        "last_assistant_message": text,
    }


def collect_modeled_user_feedback(state: BehavioralProfileState, feedback: dict[str, Any]) -> BehavioralProfileState:
    entry = dict(feedback)
    entry["timestamp"] = _utc_now()
    items = list(state.get("refinement_feedback") or [])
    items.append(entry)
    return {**state, "refinement_feedback": items}


def classify_feedback(state: BehavioralProfileState) -> BehavioralProfileState:
    last = (state.get("refinement_feedback") or [])[-1] if state.get("refinement_feedback") else {}
    needs_update = any(
        [
            int(last.get("sounds_like_me", 4)) <= 3,
            int(last.get("tone_correct", 4)) <= 3,
            int(last.get("phrasing_correct", 4)) <= 3,
            bool(last.get("too_generic")),
            bool(last.get("too_exaggerated")),
            bool(last.get("unnatural")),
            bool(last.get("contextually_incorrect")),
            bool(last.get("rewrite")),
        ]
    )
    return {**state, "status": "update_profile" if needs_update else "collecting"}


async def update_behavioral_profile(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    profile = state.get("behavioral_profile") or {}
    feedback = (state.get("refinement_feedback") or [])[-1]
    messages = [
        {"role": "system", "content": "Output valid YAML only."},
        {
            "role": "user",
            "content": PROFILE_REFINEMENT_PROMPT.format(
                profile=profile,
                feedback=feedback,
            ),
        },
    ]
    raw = await complete_chat(brain, messages)
    try:
        updated = parse_profile_yaml(raw)
        updated["profile_id"] = str(state.get("profile_id", ""))
    except ValueError:
        updated = dict(profile)
    return {**state, "behavioral_profile": updated}


def save_refinement_record(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile_id = str(state.get("profile_id", ""))
    store.save_refinement(
        profile_id,
        {
            "feedback": state.get("refinement_feedback") or [],
            "transcript": state.get("refinement_transcript") or [],
        },
    )
    return state


def save_updated_profile(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile = state.get("behavioral_profile")
    if isinstance(profile, dict):
        store.save_behavioral_yaml(profile)
    return {**state, "status": "refined"}


def _build_feedback_graph(brain: Any, store: ProfileStore):
    graph = StateGraph(BehavioralProfileState)

    async def update_node(s: BehavioralProfileState) -> BehavioralProfileState:
        s = classify_feedback(s)
        if s.get("status") == "update_profile":
            s = await update_behavioral_profile(brain, s)
            s = save_refinement_record(store, s)
            s = save_updated_profile(store, s)
        else:
            s = save_refinement_record(store, s)
        return s

    graph.add_node("process_feedback", update_node)
    graph.add_edge(START, "process_feedback")
    graph.add_edge("process_feedback", END)
    return graph.compile()


async def run_refinement_start(store: ProfileStore, *, profile_id: str) -> dict[str, Any]:
    state = default_training_state(profile_id)
    state = load_behavioral_profile(store, state)
    store.save_session(profile_id, "refinement", dict(state))
    profile = state.get("behavioral_profile") or {}
    return {
        "profile_id": profile_id,
        "status": "refinement",
        "style_summary": profile_to_style_summary(profile) if profile.get("style") else profile.get("style_summary", ""),
    }


async def run_refinement_message(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    user_message: str,
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "refinement")
    if not loaded:
        state = load_behavioral_profile(store, default_training_state(profile_id))
    else:
        state = loaded
    state = await generate_profile_based_response(brain, store, state, user_message=user_message)
    store.save_session(profile_id, "refinement", dict(state))
    return {"text": state.get("message", ""), "conversation_history": state.get("refinement_transcript") or []}


async def run_refinement_feedback(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    feedback: dict[str, Any],
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "refinement")
    if not loaded:
        raise ValueError("refinement_session_not_found")
    state = collect_modeled_user_feedback(loaded, feedback)
    graph = _build_feedback_graph(brain, store)
    state = await graph.ainvoke(state)
    store.save_session(profile_id, "refinement", dict(state))
    return {"ok": True, "status": state.get("status"), "profile_updated": state.get("status") == "refined"}


async def run_refinement_finalize(store: ProfileStore, *, profile_id: str) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "refinement")
    if loaded:
        profile = loaded.get("behavioral_profile")
        if isinstance(profile, dict):
            store.save_behavioral_yaml(profile)
    store.delete_session(profile_id, "refinement")
    return {"ok": True, "profile_id": profile_id}
