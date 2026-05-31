from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.prompts import (
    PROFILE_EXTRACTION_PROMPT,
    TRAINING_FINISH_CLOSING,
    TRAINING_MIRROR_PROMPT,
    TRAINING_OPEN_CONTINUE,
    TRAINING_OPEN_WELCOME,
    TRAINING_WRAP_SUGGEST,
)
from app.agents.training_prompts import CORE_TRAINING_PROMPTS
from app.experiment.interview import build_interview_messages, normalize_history
from app.profiles.builder import compile_behavioral
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import default_profile_template, parse_profile_yaml

INTERVIEW_SYSTEM_OPEN = """You are running an open behavioral profile training conversation in Spanish.
There is no fixed question count — follow the conversation naturally until the participant is satisfied.
Collect how they naturally talk: tone, phrases, reactions, humor, advice style.
Do not mention cloning, profiling, or AI training. Allow skips. Stay warm and human.
Ask one thing at a time."""

MIRROR_SYSTEM = """You calibrate imitation of the participant's conversational style in Spanish.
Mirror turns MUST follow this flow:
1) Preamble: "Ahora voy a tratar de imitarte y me dices qué te parece."
2) Short scenario + first-person imitation of how they would answer.
3) Follow-up: "¿Es esto algo que dirías?" (optionally ask what they would change).
Stay warm and natural. Never mention AI or profiling."""

MIN_SAMPLES_TO_FINISH = 3
MIRROR_EVERY_N_SAMPLES = 2
WRAP_SUGGEST_EVERY_N_SAMPLES = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _last_assistant(transcript: list[dict[str, Any]]) -> str:
    for item in reversed(normalize_history(transcript)):
        if item["role"] == "assistant":
            return item["content"]
    return ""


def _remaining_topics(state: BehavioralProfileState) -> list[dict[str, str]]:
    explored = set(state.get("topics_explored") or [])
    return [p for p in CORE_TRAINING_PROMPTS if p.get("id") not in explored]


def _remaining_topic_labels(state: BehavioralProfileState) -> list[str]:
    remaining = _remaining_topics(state)
    if not remaining:
        return [p.get("text", "") for p in CORE_TRAINING_PROMPTS if p.get("text")]
    return [p.get("text", "") for p in remaining if p.get("text")]


def _pick_topic(state: BehavioralProfileState) -> dict[str, str]:
    remaining = _remaining_topics(state)
    if remaining:
        return remaining[0]
    return CORE_TRAINING_PROMPTS[len(state.get("raw_samples") or []) % len(CORE_TRAINING_PROMPTS)]


def _mark_topic_explored(state: BehavioralProfileState, topic: dict[str, str]) -> BehavioralProfileState:
    explored = list(state.get("topics_explored") or [])
    topic_id = str(topic.get("id", "")).strip()
    if topic_id and topic_id not in explored:
        explored.append(topic_id)
    return {**state, "topics_explored": explored}


def initialize_training_session(state: BehavioralProfileState) -> BehavioralProfileState:
    base = default_training_state(str(state.get("profile_id", "")))
    alias = state.get("modeled_user_alias")
    if alias:
        base["modeled_user_alias"] = alias
    base["total_prompts"] = 0
    base["open_ended"] = True
    base["topics_explored"] = []
    base["samples_since_mirror"] = 0
    base["turn_mode"] = "interview"
    base["status"] = "collecting"
    base["complete"] = False
    return base


async def generate_training_message(
    brain: Any,
    state: BehavioralProfileState,
    *,
    mode: str,
    steering: str,
) -> BehavioralProfileState:
    system = MIRROR_SYSTEM if mode == "mirror" else INTERVIEW_SYSTEM_OPEN
    messages = build_interview_messages(
        system=system,
        conversation_history=state.get("interview_transcript") or [],
        steering=steering,
    )
    message = await complete_chat(brain, messages)
    transcript = list(state.get("interview_transcript") or [])
    transcript.append({"role": "assistant", "content": message})
    updates: BehavioralProfileState = {
        **state,
        "message": message,
        "last_assistant_message": message,
        "interview_transcript": transcript,
        "turn_mode": mode,
    }
    if mode == "mirror":
        updates["awaiting_mirror_feedback"] = True
        updates["last_mirror_attempt"] = message
    else:
        updates["awaiting_mirror_feedback"] = False
    return updates


def save_user_turn(
    state: BehavioralProfileState,
    *,
    user_message: str,
    skip: bool,
    was_mirror_feedback: bool,
) -> BehavioralProfileState:
    transcript = list(state.get("interview_transcript") or [])
    samples = list(state.get("raw_samples") or [])
    sample_saved = False
    samples_since_mirror = int(state.get("samples_since_mirror", 0))

    if skip:
        transcript.append({"role": "user", "content": "[skipped]"})
        return {
            **state,
            "interview_transcript": transcript,
            "raw_samples": samples,
            "sample_saved": False,
            "samples_since_mirror": samples_since_mirror,
            "awaiting_mirror_feedback": False if was_mirror_feedback else state.get("awaiting_mirror_feedback"),
        }

    if user_message.strip():
        text = user_message.strip()
        transcript.append({"role": "user", "content": text})
        asked = _last_assistant(transcript[:-1]) or ""
        if was_mirror_feedback:
            samples.append(
                {
                    "prompt_id": "mirror_calibration",
                    "category": "mirror_calibration",
                    "prompt": asked,
                    "response": text,
                    "mirror_attempt": str(state.get("last_mirror_attempt") or asked),
                    "timestamp": _utc_now(),
                    "is_follow_up": False,
                }
            )
            sample_saved = True
        else:
            topic = _pick_topic(state)
            samples.append(
                {
                    "prompt_id": topic.get("id", f"turn_{len(samples)}"),
                    "category": topic.get("category", "open"),
                    "prompt": asked or topic.get("text", ""),
                    "response": text,
                    "timestamp": _utc_now(),
                    "is_follow_up": False,
                }
            )
            state = _mark_topic_explored(state, topic)
            sample_saved = True
            samples_since_mirror += 1

    return {
        **state,
        "interview_transcript": transcript,
        "raw_samples": samples,
        "sample_saved": sample_saved,
        "samples_since_mirror": samples_since_mirror,
        "awaiting_mirror_feedback": False if was_mirror_feedback else state.get("awaiting_mirror_feedback"),
    }


def _should_mirror(state: BehavioralProfileState) -> bool:
    if state.get("complete") or state.get("awaiting_mirror_feedback"):
        return False
    return int(state.get("samples_since_mirror", 0)) >= MIRROR_EVERY_N_SAMPLES


def _should_suggest_wrap(state: BehavioralProfileState) -> bool:
    if state.get("complete"):
        return False
    count = len(state.get("raw_samples") or [])
    return count >= MIN_SAMPLES_TO_FINISH and count % WRAP_SUGGEST_EVERY_N_SAMPLES == 0


async def generate_next_turn(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    if _should_mirror(state):
        steering = TRAINING_MIRROR_PROMPT
        result = await generate_training_message(brain, state, mode="mirror", steering=steering)
        return {**result, "samples_since_mirror": 0}

    if _should_suggest_wrap(state):
        count = len(state.get("raw_samples") or [])
        steering = TRAINING_WRAP_SUGGEST.format(sample_count=count)
        return await generate_training_message(brain, state, mode="wrap_suggest", steering=steering)

    remaining = _remaining_topic_labels(state)
    if not normalize_history(state.get("interview_transcript") or []):
        steering = TRAINING_OPEN_WELCOME
    else:
        steering = TRAINING_OPEN_CONTINUE.format(
            remaining_topics="; ".join(remaining[:8]) or "everyday life, opinions, reactions, advice, humor",
        )
    return await generate_training_message(brain, state, mode="interview", steering=steering)


def finalize_raw_samples(state: BehavioralProfileState) -> BehavioralProfileState:
    return {**state, "status": "extracting"}


async def extract_behavioral_profile(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    samples_text = "\n\n".join(
        f"P: {s.get('prompt', '')}\nR: {s.get('response', '')}"
        + (f"\nMirror attempt: {s.get('mirror_attempt', '')}" if s.get("mirror_attempt") else "")
        for s in (state.get("raw_samples") or [])
    )
    messages = [
        {"role": "system", "content": "You output valid YAML behavioral profiles only."},
        {"role": "user", "content": PROFILE_EXTRACTION_PROMPT.format(samples=samples_text)},
    ]
    raw_yaml = await complete_chat(brain, messages)
    errors = list(state.get("errors") or [])
    try:
        profile = parse_profile_yaml(raw_yaml)
        profile["profile_id"] = str(state.get("profile_id", ""))
        return {**state, "behavioral_profile": profile}
    except ValueError:
        errors.append("yaml_parse_fallback")
        fallback = default_profile_template(str(state.get("profile_id", "")))
        compiled = compile_behavioral(
            {
                "profile_id": state.get("profile_id", ""),
                "modeled_user_alias": state.get("modeled_user_alias") or "",
                "samples": state.get("raw_samples") or [],
            }
        )
        fallback["style_summary"] = compiled.get("style_summary", "")
        return {**state, "behavioral_profile": fallback, "errors": errors}


def save_behavioral_profile(store: ProfileStore, state: BehavioralProfileState) -> BehavioralProfileState:
    profile_id = str(state.get("profile_id", ""))
    raw_payload = {
        "profile_id": profile_id,
        "modeled_user_alias": state.get("modeled_user_alias") or "",
        "created_at": _utc_now(),
        "consent_confirmed": True,
        "samples": state.get("raw_samples") or [],
        "interview_transcript": state.get("interview_transcript") or [],
        "open_ended": True,
    }
    store.save_raw(raw_payload)
    profile = state.get("behavioral_profile")
    if isinstance(profile, dict) and profile.get("style"):
        saved = store.save_behavioral_yaml(profile)
    else:
        saved = store.save_behavioral(compile_behavioral(raw_payload))
    return {**state, "behavioral_profile": saved, "status": "finalized"}


def _build_finalize_graph(brain: Any, store: ProfileStore):
    graph = StateGraph(BehavioralProfileState)

    async def extract_node(s: BehavioralProfileState) -> BehavioralProfileState:
        s = finalize_raw_samples(s)
        return await extract_behavioral_profile(brain, s)

    graph.add_node("extract", extract_node)
    graph.add_node("save", lambda s: save_behavioral_profile(store, s))
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "save")
    graph.add_edge("save", END)
    return graph.compile()


async def run_training_start(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    modeled_user_alias: str = "",
) -> dict[str, Any]:
    state = initialize_training_session(
        {"profile_id": profile_id, "modeled_user_alias": modeled_user_alias or None}
    )
    state = await generate_next_turn(brain, state)
    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state)


async def run_training_answer(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    user_message: str,
    skip: bool = False,
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    if loaded.get("complete"):
        raise ValueError("training_already_complete")
    was_mirror = bool(loaded.get("awaiting_mirror_feedback"))
    state = save_user_turn(loaded, user_message=user_message, skip=skip, was_mirror_feedback=was_mirror)
    state = await generate_next_turn(brain, state)
    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state)


async def run_training_finish(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    samples = loaded.get("raw_samples") or []
    if len(samples) < MIN_SAMPLES_TO_FINISH:
        raise ValueError("not_enough_samples")
    state: BehavioralProfileState = {**loaded, "complete": True, "status": "ready_to_finalize"}
    state = await generate_training_message(
        brain,
        state,
        mode="finish",
        steering=TRAINING_FINISH_CLOSING,
    )
    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state)


async def run_training_finalize(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    if not loaded.get("complete") and len(loaded.get("raw_samples") or []) < MIN_SAMPLES_TO_FINISH:
        raise ValueError("training_not_ready")
    graph = _build_finalize_graph(brain, store)
    state = await graph.ainvoke(loaded)
    store.delete_session(profile_id, "training")
    return {
        "ok": True,
        "profile_id": profile_id,
        "status": state.get("status"),
        "behavioral_profile": state.get("behavioral_profile"),
        "sample_count": len(state.get("raw_samples") or []),
    }


def _training_api_response(state: BehavioralProfileState) -> dict[str, Any]:
    samples = list(state.get("raw_samples") or [])
    return {
        "message": state.get("message", ""),
        "prompt_index": len(samples),
        "total_prompts": 0,
        "open_ended": True,
        "complete": bool(state.get("complete", False)),
        "samples": samples,
        "sample_count": len(samples),
        "min_samples_to_finish": MIN_SAMPLES_TO_FINISH,
        "sample_saved": bool(state.get("sample_saved", False)),
        "conversation_history": list(state.get("interview_transcript") or []),
        "turn_mode": state.get("turn_mode", "interview"),
        "awaiting_mirror_feedback": bool(state.get("awaiting_mirror_feedback", False)),
        "status": state.get("status", "collecting"),
    }


# Kept for smoke tests that import graph builders.
def _build_answer_graph(brain: Any):
    graph = StateGraph(BehavioralProfileState)

    async def next_node(s: BehavioralProfileState) -> BehavioralProfileState:
        return await generate_next_turn(brain, s)

    graph.add_node("next", next_node)
    graph.add_edge(START, "next")
    graph.add_edge("next", END)
    return graph.compile()


def _build_finalize_graph_export(brain: Any, store: ProfileStore):
    return _build_finalize_graph(brain, store)
