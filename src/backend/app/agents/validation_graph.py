from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.refinement_graph import RATING_KEYS
from app.agents.training_prompts import CORE_TRAINING_PROMPTS
from app.experiment.chat import run_experiment_chat
from app.profiles.store import ProfileStore

SIMILARITY_KEYS = ("tone_similarity", "phrasing_similarity", "response_length_similarity", "behavioral_consistency", "reminds_me_of_person")
THRESHOLDS = {
    "mean_similarity": 4.5,
    "mean_naturalness": 4.0,
    "mean_identity_safety": 5.5,
}


def load_behavioral_profile(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile_id = str(state.get("profile_id", ""))
    profile = store.load_final_profile(profile_id)
    if profile is None:
        raise ValueError("profile_not_found")
    return {**state, "behavioral_profile": profile, "status": "validation"}


def generate_validation_prompt(state: BehavioralProfileState) -> BehavioralProfileState:
    idx = len(state.get("validation_samples") or []) % len(CORE_TRAINING_PROMPTS)
    prompt = CORE_TRAINING_PROMPTS[idx].get("text", "Cuéntame brevemente cómo fue tu día.")
    return {**state, "validation_prompt": prompt}


async def generate_agent_response(
    brain: Any,
    store: ProfileStore,
    state: BehavioralProfileState,
) -> BehavioralProfileState:
    prompt = str(state.get("validation_prompt", ""))
    text, meta = await run_experiment_chat(
        brain,
        store,
        message=prompt,
        condition="A",
        profile_id=str(state.get("profile_id", "")),
        conversation_history=[],
    )
    samples = list(state.get("validation_samples") or [])
    samples.append(
        {
            "prompt": prompt,
            "agent_response": text,
            "metadata": meta,
        }
    )
    return {**state, "validation_samples": samples, "message": text}


def collect_validator_rating(state: BehavioralProfileState, rating: dict[str, Any]) -> BehavioralProfileState:
    results = list(state.get("validation_results") or [])
    results.append(rating)
    return {**state, "validation_results": results}


def aggregate_validation_scores(state: BehavioralProfileState) -> BehavioralProfileState:
    results = state.get("validation_results") or []
    if not results:
        return {**state, "validation_summary": {"passed": False, "n_validators": 0}}
    sim_sum = 0.0
    sim_n = 0
    natural_sum = 0.0
    identity_sum = 0.0
    for item in results:
        scores = item.get("scores") or item
        for key in SIMILARITY_KEYS:
            sim_sum += float(scores.get(key, 0))
            sim_n += 1
        natural_sum += float(scores.get("naturalness", 0))
        identity_sum += float(scores.get("identity_leakage_absent", 0))
    n = max(len(results), 1)
    mean_similarity = sim_sum / max(sim_n, 1)
    mean_naturalness = natural_sum / n
    mean_identity_safety = identity_sum / n
    passed = (
        mean_similarity >= THRESHOLDS["mean_similarity"]
        and mean_naturalness >= THRESHOLDS["mean_naturalness"]
        and mean_identity_safety >= THRESHOLDS["mean_identity_safety"]
    )
    summary = {
        "profile_id": state.get("profile_id"),
        "n_validators": len(results),
        "mean_similarity": round(mean_similarity, 2),
        "mean_naturalness": round(mean_naturalness, 2),
        "mean_identity_safety": round(mean_identity_safety, 2),
        "passed": passed,
        "thresholds": THRESHOLDS,
    }
    return {**state, "validation_summary": summary, "passed": passed, "status": "validated"}


def save_validation_results(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile_id = str(state.get("profile_id", ""))
    payload = {
        "profile_id": profile_id,
        "validation_samples": state.get("validation_samples") or [],
        "validation_results": state.get("validation_results") or [],
        "summary": state.get("validation_summary") or {},
        "passed": state.get("passed", False),
    }
    store.save_validation_aggregate(profile_id, payload)
    return state


def _build_finalize_validation_graph(store: ProfileStore):
    graph = StateGraph(BehavioralProfileState)
    graph.add_node("aggregate", aggregate_validation_scores)
    graph.add_node("save", lambda s: save_validation_results(store, s))
    graph.add_edge(START, "aggregate")
    graph.add_edge("aggregate", "save")
    graph.add_edge("save", END)
    return graph.compile()


async def run_validation_start(store: ProfileStore, *, profile_id: str) -> dict[str, Any]:
    state = load_behavioral_profile(store, default_training_state(profile_id))
    store.save_session(profile_id, "validation", dict(state))
    return {"profile_id": profile_id, "status": "validation", "rating_keys": list(RATING_KEYS)}


async def run_validation_generate(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "validation") or load_behavioral_profile(
        store, default_training_state(profile_id)
    )
    state = generate_validation_prompt(loaded)
    state = await generate_agent_response(brain, store, state)
    store.save_session(profile_id, "validation", dict(state))
    sample = (state.get("validation_samples") or [])[-1]
    return {
        "prompt": sample.get("prompt", ""),
        "agent_response": sample.get("agent_response", ""),
        "metadata": sample.get("metadata", {}),
    }


async def run_validation_rating(
    store: ProfileStore,
    *,
    profile_id: str,
    validator_id: str,
    scores: dict[str, Any],
    prompt: str = "",
    agent_response: str = "",
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "validation")
    if not loaded:
        raise ValueError("validation_session_not_found")
    rating = {
        "validator_id": validator_id,
        "prompt": prompt,
        "agent_response": agent_response,
        "scores": scores,
    }
    state = collect_validator_rating(loaded, rating)
    store.save_session(profile_id, "validation", dict(state))
    return {"ok": True, "ratings_count": len(state.get("validation_results") or [])}


async def run_validation_finalize(store: ProfileStore, *, profile_id: str) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "validation")
    if not loaded:
        raise ValueError("validation_session_not_found")
    graph = _build_finalize_validation_graph(store)
    state = await graph.ainvoke(loaded)
    store.delete_session(profile_id, "validation")
    return dict(state.get("validation_summary") or {})
