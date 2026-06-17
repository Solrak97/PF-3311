from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.brain_adapter import complete_chat
from app.agents.memory import build_llm_messages, history_to_messages
from app.agents.profile_state import BehavioralProfileState, default_training_state
from app.agents.skills.behavioral_observer import observe_exchange
from app.agents.skills.profile_builder import (
    incremental_profile_update,
    reconcile_profile_at_finalize,
)
from app.experiment.interview import normalize_history
from app.profiles.builder import compile_behavioral
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import (
    default_profile_template,
    dump_profile_yaml,
    normalize_profile_yaml,
    parse_profile_yaml,
    profile_to_style_summary,
)
from app.prompts.renderer import render_template
from app.skills.loader import SkillLoader

TRAINING_SKILL_ID = "train_profile"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_mirror_response(text: str) -> tuple[str, str]:
    """Split mirror output into (participant-facing message, imitation-only line)."""
    cleaned = text.strip()
    if not cleaned:
        return "", ""
    if "\n---\n" in cleaned:
        parts = cleaned.split("\n---\n", 1)
    elif "\n---" in cleaned:
        parts = cleaned.split("\n---", 1)
    elif "---" in cleaned:
        parts = cleaned.split("---", 1)
    else:
        return cleaned, cleaned
    display = parts[0].strip()
    imitation = parts[1].strip() if len(parts) > 1 else ""
    for prefix in (
        "BLOCK 2",
        "BLOQUE 2",
        "IMITACIÓN",
        "IMITATION",
        "Imitación:",
        "Imitation:",
    ):
        lower = imitation.lower()
        if lower.startswith(prefix.lower()):
            imitation = imitation[len(prefix) :].lstrip(": \n")
    if not imitation:
        imitation = display
    return display, imitation


def _skill_config(skills: SkillLoader) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    skill = skills.get(TRAINING_SKILL_ID)
    calibration = skill.calibration
    cycles = skill.cycles
    if not cycles:
        raise ValueError("training_skill_missing_cycles")
    return calibration, cycles


def _probes_per_cycle(calibration: dict[str, Any]) -> int:
    return int(calibration.get("probes_per_cycle", 3))


def _min_cycles(calibration: dict[str, Any]) -> int:
    return int(calibration.get("min_cycles_to_finish", 2))


def _max_refine_rounds(calibration: dict[str, Any]) -> int:
    return int(calibration.get("max_refine_rounds", 5))


def _is_continuous_mode(calibration: dict[str, Any]) -> bool:
    return str(calibration.get("mode", "cycles")).strip().lower() == "continuous"


def _min_answers_before_mirror(calibration: dict[str, Any]) -> int:
    return int(calibration.get("min_answers_before_mirror", 5))


def _min_profile_phrases_before_mirror(calibration: dict[str, Any]) -> int:
    return int(calibration.get("min_profile_phrases_before_mirror", 3))


def _profile_phrase_count(profile: dict[str, Any] | None) -> int:
    if not isinstance(profile, dict):
        return 0
    lexical = profile.get("lexical_patterns")
    if not isinstance(lexical, dict):
        return 0
    phrases = lexical.get("common_phrases") or []
    exemplars = profile.get("voice_exemplars") or []
    count = len(phrases) if isinstance(phrases, list) else 0
    if isinstance(exemplars, list):
        count += len(exemplars)
    return count


def _all_prompt_topics(skills: SkillLoader) -> list[dict[str, str]]:
    skill = skills.get(TRAINING_SKILL_ID)
    return [p for p in skill.prompts if isinstance(p, dict) and p.get("text")]


def _next_exploration_topic(state: BehavioralProfileState, skills: SkillLoader) -> dict[str, str]:
    topics = _all_prompt_topics(skills)
    if not topics:
        return {"id": "open", "category": "open", "text": "Explore how they talk in everyday chat."}
    explored = list(state.get("topics_explored") or [])
    for item in topics:
        pid = str(item.get("id", ""))
        if pid and pid not in explored:
            explored.append(pid)
            return item
    idx = len(state.get("raw_samples") or []) % len(topics)
    return topics[idx]


def _parse_turn_decision(raw: str) -> Literal["probe", "mirror"]:
    cleaned = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and str(data.get("action", "")).strip().lower() == "mirror":
            return "mirror"
    except json.JSONDecodeError:
        pass
    if re.search(r'"action"\s*:\s*"mirror"', cleaned, re.IGNORECASE):
        return "mirror"
    return "probe"


async def _decide_mirror_or_probe(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    calibration: dict[str, Any],
) -> Literal["probe", "mirror"]:
    since = int(state.get("samples_since_mirror", 0))
    min_before = _min_answers_before_mirror(calibration)
    if since < min_before:
        return "probe"
    profile = _coerce_behavioral_profile(state)
    phrase_count = _profile_phrase_count(profile)
    if phrase_count < _min_profile_phrases_before_mirror(calibration):
        return "probe"
    skill = skills.get(TRAINING_SKILL_ID)
    steering = render_template(
        skill.templates.get("turn_decision", "training_turn_decision"),
        profile_yaml=_profile_yaml_text({**state, "behavioral_profile": profile}),
        recent_summary=_probe_summary(state),
        samples_since_mirror=since,
        min_before_mirror=min_before,
        phrase_count=phrase_count,
        mirror_count=len(state.get("cycles_completed") or []),
        total_samples=len(state.get("raw_samples") or []),
    )
    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": steering},
    ]
    raw = await complete_chat(brain, messages)
    return _parse_turn_decision(raw)


async def _ask_adaptive_probe(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    skill = skills.get(TRAINING_SKILL_ID)
    topic = _next_exploration_topic(state, skills)
    topic_text = topic.get("text", "")
    explored = list(state.get("topics_explored") or [])
    pid = str(topic.get("id", ""))
    if pid and pid not in explored:
        explored.append(pid)
    transcript = state.get("interview_transcript") or []
    if not normalize_history(transcript):
        steering = render_template(
            skill.templates.get("probe_welcome", "training_probe_welcome"),
            topic=topic_text,
        )
    else:
        steering = render_template(
            skill.templates.get("probe_question", "training_probe_question"),
            topic=topic_text,
            cycle_label="conversación",
        )
    result = await _generate_message(brain, state, skills=skills, mode="probe", steering=steering)
    return {
        **result,
        "cycle_phase": "probe",
        "awaiting_verdict": False,
        "turn_mode": "probe",
        "topics_explored": explored,
        "cycle_label": "conversación continua",
        "last_topic_id": pid,
        "last_topic_category": str(topic.get("category", "open")),
    }


def _skip_mirror_continuous(state: BehavioralProfileState) -> BehavioralProfileState:
    """Abandon current imitation attempt; keep probe context and return to chat."""
    cycle_data = dict(_current_cycle_data(state))
    attempts = list(cycle_data.get("imitation_attempts") or [])
    attempts.append(
        {
            "text": str(state.get("last_imitation") or ""),
            "verdict": "skip",
            "round": int(state.get("refine_round", 0)),
        }
    )
    cycle_data["imitation_attempts"] = attempts
    return {
        **state,
        "awaiting_verdict": False,
        "cycle_phase": "probe",
        "refine_round": 0,
        "last_imitation": "",
        "samples_since_mirror": 0,
        "current_cycle_data": cycle_data,
        "turn_mode": "probe",
    }


def _accept_mirror_continuous(state: BehavioralProfileState) -> BehavioralProfileState:
    accepted = str(state.get("last_imitation") or "")
    cycle_data = dict(_current_cycle_data(state))
    attempts = list(cycle_data.get("imitation_attempts") or [])
    attempts.append({"text": accepted, "verdict": "accept", "round": int(state.get("refine_round", 0))})
    completed = list(state.get("cycles_completed") or [])
    completed.append(
        {
            "cycle_id": len(completed) + 1,
            "signal_target": "continuous",
            "label": "imitación aceptada",
            "probe": cycle_data.get("probe") or [],
            "imitation_attempts": attempts,
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
                "timestamp": _utc_now(),
            }
        )
    return {
        **state,
        "raw_samples": samples,
        "cycles_completed": completed,
        "awaiting_verdict": False,
        "cycle_phase": "probe",
        "refine_round": 0,
        "last_imitation": "",
        "samples_since_mirror": 0,
        "current_cycle_data": {"probe": [], "imitation_attempts": []},
        "turn_mode": "probe",
    }


async def _observe_latest_answer(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    samples = state.get("raw_samples") or []
    if not samples:
        return state
    last = samples[-1]
    response = str(last.get("response", "")).strip()
    if not response or response == "[skipped]":
        return state
    observation = await observe_exchange(
        brain,
        prompt=str(last.get("prompt", "")),
        response=response,
        category=str(last.get("category", "open")),
        transcript=state.get("interview_transcript") or [],
        skills=skills,
    )
    observations = list(state.get("observations") or [])
    observations.append(observation)
    signals = dict(state.get("signals_covered") or {})
    category = str(observation.get("situation_hint") or last.get("category") or "open")
    if category:
        signals[category] = True
    return {**state, "observations": observations, "signals_covered": signals}


async def _continue_after_answer_continuous(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    calibration: dict[str, Any],
) -> BehavioralProfileState:
    state = await _observe_latest_answer(brain, state, skills=skills)
    observations = state.get("observations") or []
    latest_obs = observations[-1] if observations else None
    state = await incremental_profile_update(
        brain,
        state,
        skills=skills,
        latest_observation=latest_obs if isinstance(latest_obs, dict) else None,
    )
    action = await _decide_mirror_or_probe(brain, state, skills=skills, calibration=calibration)
    if action == "mirror":
        result = await _emit_imitation(brain, state, skills=skills)
        return {**result, "turn_mode": "mirror"}
    return await _ask_adaptive_probe(brain, state, skills=skills)


def _prompt_by_id(skills: SkillLoader, prompt_id: str) -> dict[str, str]:
    return skills.prompt_by_id(TRAINING_SKILL_ID, prompt_id)


def _cycle_plan(cycles: list[dict[str, Any]], cycle_index: int) -> dict[str, Any]:
    return cycles[cycle_index % len(cycles)]


def _cycle_probe_ids(
    skills: SkillLoader,
    calibration: dict[str, Any],
    plan: dict[str, Any],
) -> list[str]:
    ids = [str(item) for item in (plan.get("prompt_ids") or [])]
    return ids[: _probes_per_cycle(calibration)]


def _last_assistant(transcript: list[dict[str, Any]]) -> str:
    for item in reversed(normalize_history(transcript)):
        if item["role"] == "assistant":
            return item["content"]
    return ""


def _current_plan(state: BehavioralProfileState, cycles: list[dict[str, Any]]) -> dict[str, Any]:
    return _cycle_plan(cycles, int(state.get("cycle_index", 0)))


def _probe_ids(
    state: BehavioralProfileState,
    skills: SkillLoader,
    calibration: dict[str, Any],
    cycles: list[dict[str, Any]],
) -> list[str]:
    return _cycle_probe_ids(skills, calibration, _current_plan(state, cycles))


def _current_cycle_data(state: BehavioralProfileState) -> dict[str, Any]:
    data = state.get("current_cycle_data")
    if isinstance(data, dict):
        return data
    return {"probe": [], "imitation_attempts": []}


def initialize_training_session(
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    calibration, cycles = _skill_config(skills)
    base = default_training_state(str(state.get("profile_id", "")))
    alias = state.get("modeled_user_alias")
    if alias:
        base["modeled_user_alias"] = alias
    probes = _probes_per_cycle(calibration)
    continuous = _is_continuous_mode(calibration)
    profile_id = str(base.get("profile_id", ""))
    base.update(
        {
            "cycle_index": 0,
            "cycle_phase": "probe",
            "cycle_signal_target": "",
            "cycle_label": "conversación continua" if continuous else "",
            "probe_questions_asked": 0,
            "probe_questions_planned": 0 if continuous else probes,
            "refine_round": 0,
            "awaiting_verdict": False,
            "last_imitation": "",
            "current_cycle_data": {"probe": [], "imitation_attempts": []},
            "cycles_completed": [],
            "signals_covered": {},
            "turn_mode": "probe",
            "status": "collecting",
            "complete": False,
            "open_ended": continuous,
            "total_prompts": 0 if continuous else probes,
            "topics_explored": [],
            "samples_since_mirror": 0,
            "behavioral_profile": normalize_profile_yaml(default_profile_template(profile_id)),
            "observations": [],
            "calibration_mode": "continuous" if continuous else "cycles",
        }
    )
    if not continuous:
        plan = _current_plan(base, cycles)
        base["cycle_signal_target"] = str(plan.get("target", ""))
        base["cycle_label"] = str(plan.get("label", ""))
    return base


def _build_training_messages(
    skills: SkillLoader,
    *,
    mode: str,
    steering: str,
    transcript: list[dict[str, Any]],
) -> list[dict[str, str]]:
    skill = skills.get(TRAINING_SKILL_ID)
    if mode in {"mirror", "refine"}:
        system = render_template(skill.templates.get("mirror_system", "training_mirror_system"))
    else:
        system = render_template(
            skill.templates.get("system", "training_system"),
            safety_rules=skill.safety_rules,
        )
    return build_llm_messages(
        system_prompt=system,
        prior_messages=history_to_messages(transcript),
        user_message=steering,
        max_turns=24,
    )


async def _generate_message(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    mode: str,
    steering: str,
) -> BehavioralProfileState:
    transcript = list(state.get("interview_transcript") or [])
    messages = _build_training_messages(
        skills,
        mode=mode,
        steering=steering,
        transcript=transcript,
    )
    raw_message = await complete_chat(brain, messages)
    message = raw_message
    last_imitation = ""
    if mode in {"mirror", "refine"}:
        display, imitation = _parse_mirror_response(raw_message)
        if display and imitation and display != imitation:
            message = f"{display}\n\n— Así lo dirías tú:\n{imitation}"
            last_imitation = imitation
        else:
            last_imitation = imitation or raw_message.strip()
    transcript.append({"role": "assistant", "content": message})
    updates: BehavioralProfileState = {
        **state,
        "message": message,
        "last_assistant_message": message,
        "interview_transcript": transcript,
        "turn_mode": mode,
    }
    if mode in {"mirror", "refine"}:
        updates["last_imitation"] = last_imitation or raw_message.strip()
        updates["awaiting_verdict"] = True
        updates["cycle_phase"] = "imitate" if mode == "mirror" else "refine"
    return updates


def _coerce_behavioral_profile(state: BehavioralProfileState) -> dict[str, Any]:
    profile_id = str(state.get("profile_id", ""))
    profile = state.get("behavioral_profile")
    if isinstance(profile, dict):
        return normalize_profile_yaml(profile)
    if isinstance(profile, str) and profile.strip():
        try:
            return normalize_profile_yaml(parse_profile_yaml(profile))
        except ValueError:
            pass
    return normalize_profile_yaml(default_profile_template(profile_id))


def _profile_yaml_text(state: BehavioralProfileState) -> str:
    return dump_profile_yaml(_coerce_behavioral_profile(state))


def _mirror_steering_prompt(state: BehavioralProfileState, *, skills: SkillLoader) -> str:
    skill = skills.get(TRAINING_SKILL_ID)
    yaml_text = _profile_yaml_text(state)
    return render_template(
        skill.templates.get("mirror", "training_mirror"),
        profile_yaml=yaml_text,
        profile=yaml_text,
        probe_summary=_probe_summary(state),
        situation_label=str(state.get("last_topic_category") or "conversación"),
    )


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


async def _ask_probe_question(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    calibration: dict[str, Any],
    cycles: list[dict[str, Any]],
) -> BehavioralProfileState:
    skill = skills.get(TRAINING_SKILL_ID)
    plan = _current_plan(state, cycles)
    probe_ids = _probe_ids(state, skills, calibration, cycles)
    asked = int(state.get("probe_questions_asked", 0))
    topic = _prompt_by_id(skills, probe_ids[asked]) if asked < len(probe_ids) else _prompt_by_id(skills, probe_ids[-1])
    topic_text = topic.get("text", "")
    if asked == 0 and not normalize_history(state.get("interview_transcript") or []):
        steering = render_template(
            skill.templates.get("probe_welcome", "training_probe_welcome"),
            topic=topic_text,
        )
    elif asked == 0 and int(state.get("cycle_index", 0)) > 0:
        steering = render_template(
            skill.templates.get("cycle_intro", "training_cycle_intro"),
            cycle_label=plan.get("label", ""),
            topic=topic_text,
        )
    else:
        steering = render_template(
            skill.templates.get("probe_question", "training_probe_question"),
            topic=topic_text,
            cycle_label=plan.get("label", ""),
        )
    topic_id = str(topic.get("id", ""))
    result = await _generate_message(brain, state, skills=skills, mode="probe", steering=steering)
    return {
        **result,
        "cycle_phase": "probe",
        "awaiting_verdict": False,
        "turn_mode": "probe",
        "probe_questions_planned": len(probe_ids),
        "cycle_label": str(plan.get("label", "")),
        "cycle_signal_target": str(plan.get("target", "")),
        "last_topic_id": topic_id,
        "last_topic_category": str(topic.get("category", "open")),
    }


async def _emit_imitation(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    state = {**state, "behavioral_profile": _coerce_behavioral_profile(state)}
    steering = _mirror_steering_prompt(state, skills=skills)
    result = await _generate_message(brain, state, skills=skills, mode="mirror", steering=steering)
    return {**result, "refine_round": 0}


async def _resume_probe_after_skipped_mirror(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    skill = skills.get(TRAINING_SKILL_ID)
    steering = render_template(
        skill.templates.get("probe_question", "training_probe_question"),
        topic="Explore a new thread — keep gathering how they talk before trying imitation again.",
        cycle_label="conversación",
    )
    steering = (
        "La imitación anterior no encajó. En español, dilo en 2 frases sin culpar al participante: "
        "seguimos charlando un poco más antes de intentar de nuevo.\n\n" + steering
    )
    result = await _generate_message(brain, state, skills=skills, mode="probe", steering=steering)
    return {**result, "turn_mode": "probe", "awaiting_verdict": False, "cycle_phase": "probe"}


async def _emit_refined_imitation(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    calibration: dict[str, Any],
    correction: str,
) -> BehavioralProfileState:
    skill = skills.get(TRAINING_SKILL_ID)
    steering = render_template(
        skill.templates.get("refine_mirror", "training_refine_mirror"),
        previous=str(state.get("last_imitation") or ""),
        correction=correction.strip(),
        probe_summary=_probe_summary(state),
    )
    refine_round = int(state.get("refine_round", 0)) + 1
    result = await _generate_message(brain, state, skills=skills, mode="refine", steering=steering)
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
    skills: SkillLoader,
    calibration: dict[str, Any],
    cycles: list[dict[str, Any]],
    user_message: str,
    skip: bool,
) -> BehavioralProfileState:
    transcript = list(state.get("interview_transcript") or [])
    samples = list(state.get("raw_samples") or [])
    cycle_data = dict(_current_cycle_data(state))
    probes = list(cycle_data.get("probe") or [])
    asked = int(state.get("probe_questions_asked", 0))
    if _is_continuous_mode(calibration):
        topic_id = str(state.get("last_topic_id", ""))
        prompt_meta = (
            _prompt_by_id(skills, topic_id)
            if topic_id
            else {"id": "open", "category": "open", "text": ""}
        )
    else:
        probe_ids = _probe_ids(state, skills, calibration, cycles)
        prompt_meta = _prompt_by_id(skills, probe_ids[min(asked, len(probe_ids) - 1)])
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
    sample_saved = bool(not skip and user_message.strip())
    samples_since = int(state.get("samples_since_mirror", 0))
    signals = dict(state.get("signals_covered") or {})
    if sample_saved:
        samples_since += 1
        category = str(prompt_meta.get("category", "open"))
        if category:
            signals[category] = True
    return {
        **state,
        "interview_transcript": transcript,
        "raw_samples": samples,
        "current_cycle_data": cycle_data,
        "probe_questions_asked": asked + 1,
        "sample_saved": sample_saved,
        "samples_since_mirror": samples_since,
        "signals_covered": signals,
    }


def _accept_cycle(state: BehavioralProfileState) -> BehavioralProfileState:
    cycle_data = dict(_current_cycle_data(state))
    accepted = str(state.get("last_imitation") or "")
    cycle_data["accepted_imitation"] = accepted
    attempts = list(cycle_data.get("imitation_attempts") or [])
    attempts.append({"text": accepted, "verdict": "accept", "round": int(state.get("refine_round", 0))})
    cycle_data["imitation_attempts"] = attempts

    plan_target = str(state.get("cycle_signal_target", ""))
    signals = dict(state.get("signals_covered") or {})
    if plan_target:
        signals[plan_target] = True

    completed = list(state.get("cycles_completed") or [])
    completed.append(
        {
            "cycle_id": int(state.get("cycle_index", 0)) + 1,
            "signal_target": plan_target,
            "label": str(state.get("cycle_label", "")),
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


async def _advance_after_cycle_accept(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    calibration: dict[str, Any],
    cycles: list[dict[str, Any]],
) -> BehavioralProfileState:
    cycle_index = int(state.get("cycle_index", 0))
    if cycle_index >= len(cycles):
        return await _generate_message(
            brain,
            {**state, "cycle_phase": "cycle_complete", "turn_mode": "wrap_suggest"},
            skills=skills,
            mode="wrap_suggest",
            steering=(
                "The participant accepted the last calibration cycle. Congratulate briefly in Spanish. "
                "Tell them they can press Finish interview to save the profile, or continue if they want."
            ),
        )

    plan = _current_plan(state, cycles)
    state = {
        **state,
        "cycle_phase": "probe",
        "probe_questions_asked": 0,
        "probe_questions_planned": len(_cycle_probe_ids(skills, calibration, plan)),
        "cycle_signal_target": str(plan.get("target", "")),
        "cycle_label": str(plan.get("label", "")),
        "turn_mode": "probe",
        "awaiting_verdict": False,
    }
    return await _ask_probe_question(
        brain,
        state,
        skills=skills,
        calibration=calibration,
        cycles=cycles,
    )


async def extract_behavioral_profile(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    skill = skills.get(TRAINING_SKILL_ID)
    cycles = state.get("cycles_completed") or []
    cycle_lines: list[str] = []
    for c in cycles:
        if not isinstance(c, dict):
            continue
        block = f"Cycle {c.get('cycle_id')}: {c.get('label')}\nAccepted: {c.get('accepted_imitation', '')}"
        attempts = c.get("imitation_attempts") or []
        feedback_lines = [
            f"  - round {a.get('round', '?')}: {a.get('user_feedback', '')}"
            for a in attempts
            if isinstance(a, dict) and a.get("user_feedback")
        ]
        if feedback_lines:
            block += "\nCorrections:\n" + "\n".join(feedback_lines)
        cycle_lines.append(block)
    cycle_text = "\n\n".join(cycle_lines)
    samples_text = "\n\n".join(
        f"P: {s.get('prompt', '')}\nR: {s.get('response', '')}"
        + (f"\nMirror: {s.get('mirror_attempt', '')}" if s.get("mirror_attempt") else "")
        for s in (state.get("raw_samples") or [])
    )
    prompt = render_template(
        skill.templates.get("extract_profile", "profile_extraction"),
        samples=samples_text + "\n\n" + cycle_text,
    )
    messages = [
        {"role": "system", "content": "You output valid YAML behavioral profiles only."},
        {"role": "user", "content": prompt},
    ]
    raw_yaml = await complete_chat(brain, messages)
    errors = list(state.get("errors") or [])
    try:
        profile = normalize_profile_yaml(parse_profile_yaml(raw_yaml))
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
        "observations": state.get("observations") or [],
        "signals_covered": state.get("signals_covered") or {},
        "calibration_cycles": True,
    }
    store.save_raw(raw_payload)
    profile = state.get("behavioral_profile")
    if isinstance(profile, dict) and isinstance(profile.get("style"), dict):
        saved = store.save_behavioral_yaml(normalize_profile_yaml(profile))
    else:
        saved = store.save_behavioral(compile_behavioral(raw_payload))
    return {**state, "behavioral_profile": saved, "status": "finalized"}


def _build_finalize_graph(brain: Any, store: ProfileStore, skills: SkillLoader):
    graph = StateGraph(BehavioralProfileState)

    async def extract_node(s: BehavioralProfileState) -> BehavioralProfileState:
        s = {**s, "status": "extracting"}
        return await extract_behavioral_profile(brain, s, skills=skills)

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
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    calibration, cycles = _skill_config(registry)
    state = initialize_training_session(
        {"profile_id": profile_id, "modeled_user_alias": modeled_user_alias or None},
        skills=registry,
    )
    if _is_continuous_mode(calibration):
        state = await _ask_adaptive_probe(brain, state, skills=registry)
    else:
        state = await _ask_probe_question(
            brain,
            state,
            skills=registry,
            calibration=calibration,
            cycles=cycles,
        )
    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state, calibration)


async def run_training_answer(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    user_message: str,
    skip: bool = False,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    calibration, cycles = _skill_config(registry)
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    if loaded.get("complete"):
        raise ValueError("training_already_complete")
    if loaded.get("awaiting_verdict"):
        raise ValueError("awaiting_verdict_use_training_verdict")
    if str(loaded.get("cycle_phase", "probe")) != "probe":
        raise ValueError("invalid_cycle_phase_for_answer")

    loaded = {**loaded, "behavioral_profile": _coerce_behavioral_profile(loaded)}
    state = _record_probe_answer(
        loaded,
        skills=registry,
        calibration=calibration,
        cycles=cycles,
        user_message=user_message,
        skip=skip,
    )

    if _is_continuous_mode(calibration):
        state = await _continue_after_answer_continuous(
            brain,
            state,
            skills=registry,
            calibration=calibration,
        )
    else:
        planned = int(state.get("probe_questions_planned", _probes_per_cycle(calibration)))
        asked = int(state.get("probe_questions_asked", 0))
        if asked < planned:
            state = await _ask_probe_question(
                brain,
                state,
                skills=registry,
                calibration=calibration,
                cycles=cycles,
            )
        else:
            state = await _emit_imitation(brain, state, skills=registry)

    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state, calibration)


async def run_training_verdict(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    verdict: str,
    user_message: str = "",
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    calibration, cycles = _skill_config(registry)
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
        if _is_continuous_mode(calibration):
            accepted_line = str(loaded.get("last_imitation") or "")
            state = _accept_mirror_continuous({**loaded, "interview_transcript": transcript})
            state = await incremental_profile_update(
                brain,
                state,
                skills=registry,
                mirror_feedback=accepted_line,
            )
            state = await _ask_adaptive_probe(brain, state, skills=registry)
        else:
            state = _accept_cycle({**loaded, "interview_transcript": transcript})
            state = await _advance_after_cycle_accept(
                brain,
                state,
                skills=registry,
                calibration=calibration,
                cycles=cycles,
            )
    elif normalized in {"skip", "skip_mirror", "reject_mirror", "continue"}:
        transcript = list(loaded.get("interview_transcript") or [])
        transcript.append({"role": "user", "content": "[skipped imitation — continue chatting]"})
        if _is_continuous_mode(calibration):
            state = _skip_mirror_continuous({**loaded, "interview_transcript": transcript})
            state = await _resume_probe_after_skipped_mirror(brain, state, skills=registry)
        else:
            raise ValueError("skip_mirror_only_continuous")
    elif normalized in {"refine", "reject", "needs_refinement"}:
        correction = user_message.strip()
        if not correction:
            raise ValueError("correction_required")
        transcript = list(loaded.get("interview_transcript") or [])
        transcript.append({"role": "user", "content": correction})
        refine_round = int(loaded.get("refine_round", 0))
        if _is_continuous_mode(calibration) and refine_round >= _max_refine_rounds(calibration):
            state = _skip_mirror_continuous({**loaded, "interview_transcript": transcript})
            state = await _resume_probe_after_skipped_mirror(brain, state, skills=registry)
        elif refine_round >= _max_refine_rounds(calibration):
            state = _accept_cycle({**loaded, "interview_transcript": transcript})
            state = await _advance_after_cycle_accept(
                brain,
                state,
                skills=registry,
                calibration=calibration,
                cycles=cycles,
            )
        else:
            state = await _emit_refined_imitation(
                brain,
                {**loaded, "interview_transcript": transcript},
                skills=registry,
                calibration=calibration,
                correction=correction,
            )
    else:
        raise ValueError("invalid_verdict")

    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state, calibration)


async def run_training_finish(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    calibration, _cycles = _skill_config(registry)
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    if loaded.get("awaiting_verdict"):
        raise ValueError("finish_blocked_awaiting_verdict")
    if not _is_continuous_mode(calibration):
        cycles = loaded.get("cycles_completed") or []
        if len(cycles) < _min_cycles(calibration):
            raise ValueError("not_enough_cycles")
    skill = registry.get(TRAINING_SKILL_ID)
    state: BehavioralProfileState = {**loaded, "complete": True, "status": "ready_to_finalize"}
    state = await _generate_message(
        brain,
        state,
        skills=registry,
        mode="finish",
        steering=render_template(skill.templates.get("finish", "training_finish")),
    )
    state["awaiting_verdict"] = False
    store.save_session(profile_id, "training", dict(state))
    return _training_api_response(state, calibration)


async def run_training_finalize(
    brain: Any,
    store: ProfileStore,
    *,
    profile_id: str,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    calibration, _cycles = _skill_config(registry)
    loaded = store.load_session(profile_id, "training")
    if not loaded:
        raise ValueError("training_session_not_found")
    continuous = _is_continuous_mode(calibration)
    if not loaded.get("complete"):
        if continuous:
            if not (loaded.get("raw_samples") or []):
                raise ValueError("training_not_ready")
        elif len(loaded.get("cycles_completed") or []) < _min_cycles(calibration):
            raise ValueError("training_not_ready")

    if continuous:
        reconciled = await reconcile_profile_at_finalize(brain, loaded, skills=registry)
        profile = normalize_profile_yaml(reconciled.get("behavioral_profile") or {})
        profile["profile_id"] = profile_id
        state = save_behavioral_profile(
            store,
            {
                **reconciled,
                "behavioral_profile": profile,
                "status": "finalized",
            },
        )
        from app.profiles.moment_index import build_and_save_moment_index

        await build_and_save_moment_index(brain, store, profile_id, reconciled)
    else:
        graph = _build_finalize_graph(brain, store, registry)
        state = await graph.ainvoke(loaded)
        from app.profiles.moment_index import build_and_save_moment_index

        await build_and_save_moment_index(brain, store, profile_id, state)
    store.delete_session(profile_id, "training")
    return {
        "ok": True,
        "profile_id": profile_id,
        "status": state.get("status"),
        "behavioral_profile": state.get("behavioral_profile"),
        "sample_count": len(state.get("raw_samples") or []),
        "cycles_completed": len(state.get("cycles_completed") or []),
    }


def _training_api_response(state: BehavioralProfileState, calibration: dict[str, Any]) -> dict[str, Any]:
    continuous = _is_continuous_mode(calibration)
    probes_per_cycle = _probes_per_cycle(calibration)
    min_cycles = _min_cycles(calibration)
    samples = list(state.get("raw_samples") or [])
    cycles = list(state.get("cycles_completed") or [])
    asked = int(state.get("probe_questions_asked", 0))
    planned = int(state.get("probe_questions_planned", probes_per_cycle))
    since_mirror = int(state.get("samples_since_mirror", 0))
    profile = state.get("behavioral_profile")
    style_summary = ""
    if isinstance(profile, dict):
        style_summary = profile_to_style_summary(profile)
    probe_progress = (
        f"{since_mirror} resp. desde última imitación · {len(samples)} total"
        if continuous
        else f"{min(asked, planned)}/{planned}"
    )
    return {
        "message": state.get("message", ""),
        "prompt_index": asked,
        "total_prompts": 0 if continuous else planned,
        "open_ended": continuous,
        "calibration_cycles": not continuous,
        "calibration_mode": "continuous" if continuous else "cycles",
        "complete": bool(state.get("complete", False)),
        "samples": samples,
        "sample_count": len(samples),
        "cycles_completed": cycles,
        "cycle_count": len(cycles),
        "mirror_count": len(cycles),
        "samples_since_mirror": since_mirror,
        "min_cycles_to_finish": 0 if continuous else min_cycles,
        "min_samples_to_finish": 0 if continuous else min_cycles,
        "sample_saved": bool(state.get("sample_saved", False)),
        "conversation_history": list(state.get("interview_transcript") or []),
        "turn_mode": state.get("turn_mode", "probe"),
        "cycle_phase": state.get("cycle_phase", "probe"),
        "cycle_index": int(state.get("cycle_index", 0)) + 1,
        "cycle_label": state.get("cycle_label", ""),
        "probe_progress": probe_progress,
        "awaiting_verdict": bool(state.get("awaiting_verdict", False)),
        "awaiting_mirror_feedback": bool(state.get("awaiting_verdict", False)),
        "refine_round": int(state.get("refine_round", 0)),
        "status": state.get("status", "collecting"),
        "style_summary": style_summary,
        "profile_draft_ready": isinstance(profile, dict) and bool(samples),
    }
