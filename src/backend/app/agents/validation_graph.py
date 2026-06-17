from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.ai_judge import judge_profile_response
from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.refinement_graph import RATING_KEYS
from app.experiment.chat import run_experiment_chat
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader

TRAINING_SKILL_ID = "train_profile"

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


def generate_validation_prompt(
    state: BehavioralProfileState,
    *,
    skills: SkillLoader | None = None,
) -> BehavioralProfileState:
    registry = skills or SkillLoader()
    prompts = registry.get(TRAINING_SKILL_ID).prompts
    if not prompts:
        return {**state, "validation_prompt": "Cuéntame brevemente cómo fue tu día."}
    idx = len(state.get("validation_samples") or []) % len(prompts)
    prompt = str(prompts[idx].get("text", "Cuéntame brevemente cómo fue tu día."))
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
    state = generate_validation_prompt(loaded, skills=SkillLoader())
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


async def run_validation_ai_judge(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    prompt: str = "",
    agent_response: str = "",
    generate_if_missing: bool = True,
) -> dict[str, Any]:
    """Score a validation sample with the LLM judge (validator_id=ai-judge)."""
    loaded = store.load_session(profile_id, "validation")
    if loaded is None:
        loaded = load_behavioral_profile(store, default_training_state(profile_id))
        store.save_session(profile_id, "validation", dict(loaded))

    profile = loaded.get("behavioral_profile")
    if not isinstance(profile, dict):
        profile = store.load_final_profile(profile_id)
    if profile is None:
        raise ValueError("profile_not_found")

    use_prompt = prompt.strip()
    use_response = agent_response.strip()
    if not use_prompt or not use_response:
        samples = list(loaded.get("validation_samples") or [])
        if samples:
            last = samples[-1]
            use_prompt = use_prompt or str(last.get("prompt", ""))
            use_response = use_response or str(last.get("agent_response", ""))
        elif generate_if_missing:
            generated = await run_validation_generate(brain, store, profile_id=profile_id)
            use_prompt = str(generated.get("prompt", ""))
            use_response = str(generated.get("agent_response", ""))
            loaded = store.load_session(profile_id, "validation") or loaded

    if not use_prompt or not use_response:
        raise ValueError("missing_prompt_or_agent_response")

    judged = await judge_profile_response(
        brain,
        profile=profile,
        prompt=use_prompt,
        agent_response=use_response,
    )
    await run_validation_rating(
        store,
        profile_id=profile_id,
        validator_id=str(judged.get("validator_id", "ai-judge")),
        scores=judged["scores"],
        prompt=use_prompt,
        agent_response=use_response,
    )
    return {
        "ok": True,
        "profile_id": profile_id,
        "prompt": use_prompt,
        "agent_response": use_response,
        "validator_id": judged.get("validator_id", "ai-judge"),
        "scores": judged["scores"],
        "rationale": judged.get("rationale", ""),
    }


async def run_validation_auto_test(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    samples: int = 1,
    finalize: bool = False,
) -> dict[str, Any]:
    """Generate N samples, score each with the AI judge, optionally finalize."""
    await run_validation_start(store, profile_id=profile_id)
    judgements: list[dict[str, Any]] = []
    for _ in range(max(1, samples)):
        await run_validation_generate(brain, store, profile_id=profile_id)
        judged = await run_validation_ai_judge(
            brain,
            store,
            profile_id=profile_id,
            generate_if_missing=False,
        )
        judgements.append(judged)
    result: dict[str, Any] = {
        "profile_id": profile_id,
        "samples_judged": len(judgements),
        "judgements": judgements,
    }
    if finalize:
        result["summary"] = await run_validation_finalize(store, profile_id=profile_id)
    return result


async def run_validation_finalize(store: ProfileStore, *, profile_id: str) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "validation")
    if not loaded:
        raise ValueError("validation_session_not_found")
    graph = _build_finalize_validation_graph(store)
    state = await graph.ainvoke(loaded)
    store.delete_session(profile_id, "validation")
    return dict(state.get("validation_summary") or {})
