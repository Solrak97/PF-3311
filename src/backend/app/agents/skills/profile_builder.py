from __future__ import annotations

from typing import Any

from app.agents.brain_adapter import complete_chat
from app.agents.profile_state import BehavioralProfileState
from app.agents.skills.behavioral_observer import merge_observation_into_situation_modes
from app.profiles.builder import compile_behavioral
from app.profiles.yaml_profile import (
    default_profile_template,
    dump_profile_yaml,
    normalize_profile_yaml,
    parse_profile_yaml,
    sanitize_grounded_phrases,
)
from app.prompts.renderer import render_template
from app.skills.loader import SkillLoader

TRAINING_SKILL_ID = "train_profile"


async def incremental_profile_update(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
    mirror_feedback: str = "",
    latest_observation: dict[str, Any] | None = None,
) -> BehavioralProfileState:
    """Skill 2: merge observations and latest exchange into live YAML profile."""
    skill = skills.get(TRAINING_SKILL_ID)
    profile_id = str(state.get("profile_id", ""))
    profile = state.get("behavioral_profile")
    if not isinstance(profile, dict):
        profile = default_profile_template(profile_id)
    errors = list(state.get("errors") or [])

    if mirror_feedback.strip():
        prompt = render_template(
            skill.templates.get("refine_profile", "profile_refinement"),
            profile=dump_profile_yaml(normalize_profile_yaml(profile)),
            feedback=f"Accepted imitation line:\n{mirror_feedback.strip()}",
        )
    else:
        samples = state.get("raw_samples") or []
        if not samples:
            updated = normalize_profile_yaml(profile)
            if latest_observation:
                updated = merge_observation_into_situation_modes(updated, latest_observation)
            updated = sanitize_grounded_phrases(updated)
            return {**state, "behavioral_profile": updated}
        last = samples[-1]
        if str(last.get("response", "")).strip() in {"", "[skipped]"}:
            return state
        prompt = render_template(
            skill.templates.get("profile_incremental", "training_profile_incremental"),
            profile_yaml=dump_profile_yaml(normalize_profile_yaml(profile)),
            prompt=str(last.get("prompt", "")),
            response=str(last.get("response", "")),
            total_samples=len(samples),
            observation=latest_observation or {},
        )

    messages = [
        {"role": "system", "content": "You output valid YAML behavioral profiles only."},
        {"role": "user", "content": prompt},
    ]
    raw_yaml = await complete_chat(brain, messages)
    try:
        updated = normalize_profile_yaml(parse_profile_yaml(raw_yaml))
        updated["profile_id"] = profile_id
        if latest_observation:
            updated = merge_observation_into_situation_modes(updated, latest_observation)
        updated = sanitize_grounded_phrases(updated)
        return {**state, "behavioral_profile": updated, "status": "profile_draft"}
    except ValueError:
        errors.append("incremental_profile_parse_failed")
        fallback = normalize_profile_yaml(profile)
        if latest_observation:
            fallback = merge_observation_into_situation_modes(fallback, latest_observation)
        return {**state, "behavioral_profile": fallback, "errors": errors}


async def reconcile_profile_at_finalize(
    brain: Any,
    state: BehavioralProfileState,
    *,
    skills: SkillLoader,
) -> BehavioralProfileState:
    """Batch reconciliation pass — fixes incremental drift before save."""
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
    observations = state.get("observations") or []
    obs_text = "\n".join(
        f"- {o.get('situation_hint', o.get('category', 'open'))}: "
        f"reasoning={o.get('reasoning_style', [])}; habits={o.get('conversational_habits', [])}"
        for o in observations
        if isinstance(o, dict)
    )
    samples_text = "\n\n".join(
        f"P: {s.get('prompt', '')}\nR: {s.get('response', '')}"
        + (f"\nMirror: {s.get('mirror_attempt', '')}" if s.get("mirror_attempt") else "")
        for s in (state.get("raw_samples") or [])
    )
    draft = state.get("behavioral_profile")
    draft_yaml = ""
    if isinstance(draft, dict):
        draft_yaml = dump_profile_yaml(normalize_profile_yaml(draft))
    prompt = render_template(
        skill.templates.get("extract_profile", "profile_extraction"),
        samples=samples_text + "\n\n" + "\n\n".join(cycle_lines),
        observations=obs_text,
        draft_profile=draft_yaml,
    )
    messages = [
        {"role": "system", "content": "You output valid YAML behavioral profiles only."},
        {"role": "user", "content": prompt},
    ]
    raw_yaml = await complete_chat(brain, messages)
    errors = list(state.get("errors") or [])
    profile_id = str(state.get("profile_id", ""))
    try:
        profile = normalize_profile_yaml(parse_profile_yaml(raw_yaml))
        profile["profile_id"] = profile_id
        if isinstance(draft, dict) and isinstance(draft.get("situation_modes"), dict):
            existing_modes = draft["situation_modes"]
            merged_modes = dict(profile.get("situation_modes") or {})
            for key, value in existing_modes.items():
                if key not in merged_modes and isinstance(value, dict):
                    merged_modes[key] = value
            profile["situation_modes"] = merged_modes
        profile = sanitize_grounded_phrases(profile)
        return {**state, "behavioral_profile": profile}
    except ValueError:
        errors.append("finalize_reconcile_fallback")
        if isinstance(draft, dict):
            return {**state, "behavioral_profile": sanitize_grounded_phrases(normalize_profile_yaml(draft)), "errors": errors}
        fallback = default_profile_template(profile_id)
        compiled = compile_behavioral(
            {
                "profile_id": profile_id,
                "modeled_user_alias": state.get("modeled_user_alias") or "",
                "samples": state.get("raw_samples") or [],
            }
        )
        fallback["style_summary"] = compiled.get("style_summary", "")
        return {**state, "behavioral_profile": fallback, "errors": errors}
