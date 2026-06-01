from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.prompts import (
    PROFILE_EXTRACTION_PROMPT,
    TRAINING_CYCLE_INTRO,
    TRAINING_FINISH_CLOSING,
    TRAINING_MIRROR_PROMPT,
    TRAINING_PROBE_QUESTION,
    TRAINING_PROBE_WELCOME,
    TRAINING_REFINE_IMITATION,
)
from app.agents.training_cycles import (
    CYCLE_PLANS,
    MIN_CYCLES_TO_FINISH,
    MAX_REFINE_ROUNDS,
    PROBES_PER_CYCLE,
    cycle_plan,
    cycle_probe_ids,
    prompt_by_id,
)
from app.experiment.interview import build_interview_messages, normalize_history
from app.profiles.builder import compile_behavioral
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import default_profile_template, parse_profile_yaml

INTERVIEW_SYSTEM = """You run a behavioral profile calibration interview in Spanish.
Each cycle: 2–3 short questions, then you imitate how the participant talks and they correct you.
Do not mention cloning, profiling, or AI training. Allow skips. One message at a time."""

MIRROR_SYSTEM = """You calibrate imitation of the participant's conversational style in Spanish.
Follow the mirror structure exactly. Never mention AI or profiling."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _last_assistant(transcript: list[dict[str, Any]]) -> str:
    for item in reversed(normalize_history(transcript)):
        if item["role"] == "assistant":
            return item["content"]
    return ""


def _current_plan(state: BehavioralProfileState) -> dict[str, Any]:
    return cycle_plan(int(state.get("cycle_index", 0)))


def _probe_ids(state: BehavioralProfileState) -> list[str]:
    return cycle_probe_ids(_current_plan(state))


def _current_cycle_data(state: BehavioralProfileState) -> dict[str, Any]:
    data = state.get("current_cycle_data")
    if isinstance(data, dict):
        return data
    return {"probe": [], "imitation_attempts": []}


def initialize_training_session(state: BehavioralProfileState) -> BehavioralProfileState:
    base = default_training_state(str(state.get("profile_id", "")))
    alias = state.get("modeled_user_alias")
    if alias:
        base["modeled_user_alias"] = alias
    base.update(
        {
            "cycle_index": 0,
            "cycle_phase": "probe",
            "cycle_signal_target": "",
            "cycle_label": "",
            "probe_questions_asked": 0,
            "probe_questions_planned": PROBES_PER_CYCLE,
            "refine_round": 0,
            "awaiting_verdict": False,
            "last_imitation": "",
            "current_cycle_data": {"probe": [], "imitation_attempts": []},
            "cycles_completed": [],
            "signals_covered": {},
            "turn_mode": "probe",
            "status": "collecting",
            "complete": False,
            "open_ended": False,
            "total_prompts": PROBES_PER_CYCLE,
        }
    )
    plan = _current_plan(base)
    base["cycle_signal_target"] = str(plan.get("target", ""))
    base["cycle_label"] = str(plan.get("label", ""))
    return base


async def _generate_message(
    brain: Any,
    state: BehavioralProfileState,
    *,
    mode: str,
    steering: str,
    system: str | None = None,
) -> BehavioralProfileState:
    sys_prompt = system or (MIRROR_SYSTEM if mode in {"mirror", "refine"} else INTERVIEW_SYSTEM)
    messages = build_interview_messages(
        system=sys_prompt,
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
    if mode in {"mirror", "refine"}:
        updates["last_imitation"] = message
        updates["awaiting_verdict"] = True
        updates["cycle_phase"] = "imitate" if mode == "mirror" else "refine"
    return updates


def _probe_summary(state: BehavioralProfileState) -> str:
    probes = _current_cycle_data(state).get("probe") or []
    lines: list[str] = []
    for item in probes:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt", "")).strip()
        response = str(item.get("response", "")).strip()
        if response and response != "[skipped]":
            lines.append(f"P: {prompt}\nR: {response}")
    return "\n\n".join(lines) or "(no answers yet)"


async def _ask_probe_question(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    plan = _current_plan(state)
    probe_ids = _probe_ids(state)
    asked = int(state.get("probe_questions_asked", 0))
    topic = prompt_by_id(probe_ids[asked]) if asked < len(probe_ids) else prompt_by_id(probe_ids[-1])
    topic_text = topic.get("text", "")
    if asked == 0 and not normalize_history(state.get("interview_transcript") or []):
        steering = TRAINING_PROBE_WELCOME.format(topic=topic_text)
    elif asked == 0 and int(state.get("cycle_index", 0)) > 0:
        steering = TRAINING_CYCLE_INTRO.format(
            cycle_label=plan.get("label", ""),
            topic=topic_text,
        )
    else:
        steering = TRAINING_PROBE_QUESTION.format(
            topic=topic_text,
            cycle_label=plan.get("label", ""),
        )
    result = await _generate_message(brain, state, mode="probe", steering=steering)
    return {
        **result,
        "cycle_phase": "probe",
        "awaiting_verdict": False,
        "turn_mode": "probe",
        "probe_questions_planned": len(probe_ids),
        "cycle_label": str(plan.get("label", "")),
        "cycle_signal_target": str(plan.get("target", "")),
    }


async def _emit_imitation(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    steering = TRAINING_MIRROR_PROMPT.format(probe_summary=_probe_summary(state))
    return await _generate_message(brain, state, mode="mirror", steering=steering)


async def _emit_refined_imitation(
    brain: Any,
    state: BehavioralProfileState,
    *,
    correction: str,
) -> BehavioralProfileState:
    steering = TRAINING_REFINE_IMITATION.format(
        previous=str(state.get("last_imitation") or ""),
        correction=correction.strip(),
    )
    refine_round = int(state.get("refine_round", 0)) + 1
    result = await _generate_message(brain, state, mode="refine", steering=steering)
    cycle_data = dict(_current_cycle_data(state))
    attempts = list(cycle_data.get("imitation_attempts") or [])
    attempts.append(
        {
            "text": str(state.get("last_imitation") or ""),
            "user_feedback": correction.strip(),
            "verdict": "refine",
            "round": refine_round,
        }
    )
    cycle_data["imitation_attempts"] = attempts
    return {**result, "refine_round": refine_round, "current_cycle_data": cycle_data}


def _record_probe_answer(
    state: BehavioralProfileState,
    *,
    user_message: str,
    skip: bool,
) -> BehavioralProfileState:
    transcript = list(state.get("interview_transcript") or [])
    samples = list(state.get("raw_samples") or [])
    cycle_data = dict(_current_cycle_data(state))
    probes = list(cycle_data.get("probe") or [])
    asked = int(state.get("probe_questions_asked", 0))
    probe_ids = _probe_ids(state)
    prompt_meta = prompt_by_id(probe_ids[min(asked, len(probe_ids) - 1)])
    asked_text = _last_assistant(transcript) or prompt_meta.get("text", "")

    if skip:
        transcript.append({"role": "user", "content": "[skipped]"})
        probes.append(
            {
                "prompt_id": prompt_meta.get("id", ""),
                "prompt": asked_text,
                "response": "[skipped]",
                "timestamp": _utc_now(),
            }
        )
    elif user_message.strip():
        text = user_message.strip()
        transcript.append({"role": "user", "content": text})
        probes.append(
            {
                "prompt_id": prompt_meta.get("id", ""),
                "category": prompt_meta.get("category", "open"),
                "prompt": asked_text,
                "response": text,
                "timestamp": _utc_now(),
            }
        )
        samples.append(
            {
                "prompt_id": prompt_meta.get("id", ""),
                "category": prompt_meta.get("category", "open"),
                "prompt": asked_text,
                "response": text,
                "timestamp": _utc_now(),
                "cycle_index": int(state.get("cycle_index", 0)),
            }
        )

    cycle_data["probe"] = probes
    return {
        **state,
        "interview_transcript": transcript,
        "raw_samples": samples,
        "current_cycle_data": cycle_data,
        "probe_questions_asked": asked + 1,
        "sample_saved": bool(not skip and user_message.strip()),
    }


def _accept_cycle(state: BehavioralProfileState) -> BehavioralProfileState:
    cycle_data = dict(_current_cycle_data(state))
    accepted = str(state.get("last_imitation") or "")
    cycle_data["accepted_imitation"] = accepted
    attempts = list(cycle_data.get("imitation_attempts") or [])
    attempts.append({"text": accepted, "verdict": "accept", "round": int(state.get("refine_round", 0))})
    cycle_data["imitation_attempts"] = attempts

    plan = _current_plan(state)
    target = str(plan.get("target", ""))
    signals = dict(state.get("signals_covered") or {})
    if target:
        signals[target] = True

    completed = list(state.get("cycles_completed") or [])
    completed.append(
        {
            "cycle_id": int(state.get("cycle_index", 0)) + 1,
            "signal_target": target,
            "label": str(plan.get("label", "")),
            "probe": cycle_data.get("probe") or [],
            "imitation_attempts": cycle_data.get("imitation_attempts") or [],
            "accepted_imitation": accepted,
        }
    )

    samples = list(state.get("raw_samples") or [])
    if accepted:
        samples.append(
            {
                "prompt_id": "mirror_calibration",
                "category": "mirror_calibration",
                "prompt": _probe_summary(state),
                "response": accepted,
                "mirror_attempt": accepted,
                "verdict": "accept",
                "cycle_index": int(state.get("cycle_index", 0)),
                "timestamp": _utc_now(),
            }
        )

    return {
        **state,
        "raw_samples": samples,
        "cycles_completed": completed,
        "signals_covered": signals,
        "awaiting_verdict": False,
        "cycle_phase": "cycle_complete",
        "refine_round": 0,
        "last_imitation": "",
        "current_cycle_data": {"probe": [], "imitation_attempts": []},
        "cycle_index": int(state.get("cycle_index", 0)) + 1,
    }


async def _advance_after_cycle_accept(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    cycle_index = int(state.get("cycle_index", 0))
    if cycle_index >= len(CYCLE_PLANS):
        return await _generate_message(
            brain,
            {**state, "cycle_phase": "cycle_complete", "turn_mode": "wrap_suggest"},
            mode="wrap_suggest",
            steering=(
                "The participant accepted the last calibration cycle. Congratulate briefly in Spanish. "
                "Tell them they can press Finish interview to save the profile, or continue if they want."
            ),
        )

    plan = _current_plan(state)
    state = {
        **state,
        "cycle_phase": "probe",
        "probe_questions_asked": 0,
        "probe_questions_planned": len(_probe_ids(state)),
        "cycle_signal_target": str(plan.get("target", "")),
        "cycle_label": str(plan.get("label", "")),
        "turn_mode": "probe",
        "awaiting_verdict": False,
    }
    return await _ask_probe_question(brain, state)


def finalize_raw_samples(state: BehavioralProfileState) -> BehavioralProfileState:
    return {**state, "status": "extracting"}


async def extract_behavioral_profile(brain: Any, state: BehavioralProfileState) -> BehavioralProfileState:
    cycles = state.get("cycles_completed") or []
    cycle_text = "\n\n".join(
        f"Cycle {c.get('cycle_id')}: {c.get('label')}\nAccepted: {c.get('accepted_imitation', '')}"
        for c in cycles
        if isinstance(c, dict)
    )
    samples_text = "\n\n".join(
        f"P: {s.get('prompt', '')}\nR: {s.get('response', '')}"
        + (f"\nMirror: {s.get('mirror_attempt', '')}" if s.get("mirror_attempt") else "")
        for s in (state.get("raw_samples") or [])
    )
    messages = [
        {"role": "system", "content": "You output valid YAML behavioral profiles only."},
        {
            "role": "user",
            "content": PROFILE_EXTRACTION_PROMPT.format(samples=samples_text + "\n\n" + cycle_text),
        },
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
        "cycles_completed": state.get("cycles_completed") or [],
        "interview_transcript": state.get("interview_transcript") or [],
        "calibration_cycles": True,
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
    state = await _ask_probe_question(brain, state)
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
    if loaded.get("awaiting_verdict"):
        raise ValueError("awaiting_verdict_use_training_verdict")
    if str(loaded.get("cycle_phase", "probe")) != "probe":
        raise ValueError("invalid_cycle_phase_for_answer")

    state = _record_probe_answer(loaded, user_message=user_message, skip=skip)
    planned = int(state.get("probe_questions_planned", PROBES_PER_CYCLE))
    asked = int(state.get("probe_questions_asked", 0))

    if asked < planned:
        state = await _ask_probe_question(brain, state)
    else:
        state = await _emit_imitation(brain, state)

    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state)


async def run_training_verdict(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    verdict: str,
    user_message: str = "",
) -> dict[str, Any]:
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    if loaded.get("complete"):
        raise ValueError("training_already_complete")
    if not loaded.get("awaiting_verdict"):
        raise ValueError("not_awaiting_verdict")

    normalized = verdict.strip().lower()
    if normalized == "accept":
        transcript = list(loaded.get("interview_transcript") or [])
        transcript.append({"role": "user", "content": "[accepted imitation]"})
        state = _accept_cycle({**loaded, "interview_transcript": transcript})
        state = await _advance_after_cycle_accept(brain, state)
    elif normalized in {"refine", "reject", "needs_refinement"}:
        correction = user_message.strip()
        if not correction:
            raise ValueError("correction_required")
        transcript = list(loaded.get("interview_transcript") or [])
        transcript.append({"role": "user", "content": correction})
        refine_round = int(loaded.get("refine_round", 0))
        if refine_round >= MAX_REFINE_ROUNDS:
            state = _accept_cycle({**loaded, "interview_transcript": transcript})
            state = await _advance_after_cycle_accept(brain, state)
        else:
            state = await _emit_refined_imitation(
                brain,
                {**loaded, "interview_transcript": transcript},
                correction=correction,
            )
    else:
        raise ValueError("invalid_verdict")

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
    if loaded.get("awaiting_verdict"):
        raise ValueError("finish_blocked_awaiting_verdict")
    cycles = loaded.get("cycles_completed") or []
    if len(cycles) < MIN_CYCLES_TO_FINISH:
        raise ValueError("not_enough_cycles")
    state: BehavioralProfileState = {**loaded, "complete": True, "status": "ready_to_finalize"}
    state = await _generate_message(
        brain,
        state,
        mode="finish",
        steering=TRAINING_FINISH_CLOSING,
    )
    state["awaiting_verdict"] = False
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
    if not loaded.get("complete") and len(loaded.get("cycles_completed") or []) < MIN_CYCLES_TO_FINISH:
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
        "cycles_completed": len(state.get("cycles_completed") or []),
    }


def _training_api_response(state: BehavioralProfileState) -> dict[str, Any]:
    samples = list(state.get("raw_samples") or [])
    cycles = list(state.get("cycles_completed") or [])
    asked = int(state.get("probe_questions_asked", 0))
    planned = int(state.get("probe_questions_planned", PROBES_PER_CYCLE))
    return {
        "message": state.get("message", ""),
        "prompt_index": asked,
        "total_prompts": planned,
        "open_ended": False,
        "calibration_cycles": True,
        "complete": bool(state.get("complete", False)),
        "samples": samples,
        "sample_count": len(samples),
        "cycles_completed": cycles,
        "cycle_count": len(cycles),
        "min_cycles_to_finish": MIN_CYCLES_TO_FINISH,
        "min_samples_to_finish": MIN_CYCLES_TO_FINISH,
        "sample_saved": bool(state.get("sample_saved", False)),
        "conversation_history": list(state.get("interview_transcript") or []),
        "turn_mode": state.get("turn_mode", "probe"),
        "cycle_phase": state.get("cycle_phase", "probe"),
        "cycle_index": int(state.get("cycle_index", 0)) + 1,
        "cycle_label": state.get("cycle_label", ""),
        "probe_progress": f"{min(asked, planned)}/{planned}",
        "awaiting_verdict": bool(state.get("awaiting_verdict", False)),
        "awaiting_mirror_feedback": bool(state.get("awaiting_verdict", False)),
        "refine_round": int(state.get("refine_round", 0)),
        "status": state.get("status", "collecting"),
    }


def _build_answer_graph(brain: Any):
    graph = StateGraph(BehavioralProfileState)

    async def next_node(s: BehavioralProfileState) -> BehavioralProfileState:
        if s.get("awaiting_verdict"):
            return s
        if str(s.get("cycle_phase")) == "probe":
            return await _ask_probe_question(brain, s)
        return await _emit_imitation(brain, s)

    graph.add_node("next", next_node)
    graph.add_edge(START, "next")
    graph.add_edge("next", END)
    return graph.compile()


def _build_finalize_graph_export(brain: Any, store: ProfileStore):
    return _build_finalize_graph(brain, store)
