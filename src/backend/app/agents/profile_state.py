from __future__ import annotations

from typing import Any, TypedDict


class BehavioralProfileState(TypedDict, total=False):
    profile_id: str
    modeled_user_alias: str | None
    consent_confirmed: bool
    raw_samples: list[dict[str, Any]]
    interview_transcript: list[dict[str, str]]
    current_prompt_index: int
    awaiting_follow_up: bool
    follow_up_dimension: str
    last_assistant_message: str
    behavioral_profile: dict[str, Any] | None
    refinement_feedback: list[dict[str, Any]]
    refinement_transcript: list[dict[str, str]]
    validation_samples: list[dict[str, Any]]
    validation_results: list[dict[str, Any]]
    validation_prompt: str
    status: str
    errors: list[str]
    message: str
    complete: bool
    total_prompts: int
    open_ended: bool
    turn_mode: str
    topics_explored: list[str]
    samples_since_mirror: int
    awaiting_mirror_feedback: bool
    last_mirror_attempt: str
    cycle_index: int
    cycle_phase: str
    cycle_signal_target: str
    cycle_label: str
    probe_questions_asked: int
    probe_questions_planned: int
    refine_round: int
    awaiting_verdict: bool
    last_imitation: str
    current_cycle_data: dict[str, Any]
    cycles_completed: list[dict[str, Any]]
    signals_covered: dict[str, bool]
    observations: list[dict[str, Any]]
    calibration_cycles: bool
    sample_saved: bool
    passed: bool
    validation_summary: dict[str, Any]


def default_training_state(profile_id: str, modeled_user_alias: str = "") -> BehavioralProfileState:
    return {
        "profile_id": profile_id,
        "modeled_user_alias": modeled_user_alias or None,
        "consent_confirmed": True,
        "raw_samples": [],
        "interview_transcript": [],
        "current_prompt_index": 0,
        "awaiting_follow_up": False,
        "follow_up_dimension": "",
        "behavioral_profile": None,
        "refinement_feedback": [],
        "refinement_transcript": [],
        "validation_samples": [],
        "validation_results": [],
        "status": "collecting",
        "errors": [],
        "complete": False,
        "total_prompts": 0,
        "open_ended": True,
        "turn_mode": "interview",
        "topics_explored": [],
        "samples_since_mirror": 0,
        "awaiting_mirror_feedback": False,
        "last_mirror_attempt": "",
        "cycle_index": 0,
        "cycle_phase": "probe",
        "cycle_signal_target": "",
        "cycle_label": "",
        "probe_questions_asked": 0,
        "probe_questions_planned": 5,
        "refine_round": 0,
        "awaiting_verdict": False,
        "last_imitation": "",
        "current_cycle_data": {"probe": [], "imitation_attempts": []},
        "cycles_completed": [],
        "signals_covered": {},
        "observations": [],
        "calibration_cycles": True,
    }
