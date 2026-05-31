from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

INTERVIEW_SYSTEM_PROMPT = """You are running a behavioral profile training interview.

Your goal is to collect natural conversational samples from the modeled user.
Do not analyze the user during the interview.
Do not mention cloning or behavioral profiling.
Do not ask sensitive questions.
Ask one prompt at a time.
Keep the interaction relaxed and neutral.
Allow the user to skip any question.

Respond in Spanish unless the user writes in another language.
Keep replies short: a brief acknowledgment (when appropriate) and one clear question.
Do not list multiple questions at once.
Sound like a friendly interviewer, not a form or checklist."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_interview_skill(registry: SkillRegistry | None = None) -> dict[str, Any]:
    reg = registry or SkillRegistry()
    skill = reg.get_skill("collect_modeled_user_samples")
    if not skill:
        raise ValueError("interview_skill_not_found")
    return skill


def _prompt_items(skill: dict[str, Any]) -> list[dict[str, Any]]:
    prompts = skill.get("prompts") or []
    if not isinstance(prompts, list):
        return []
    return [p for p in prompts if isinstance(p, dict)]


def _safety_block(skill: dict[str, Any]) -> str:
    rules = skill.get("safety_rules") or []
    if not isinstance(rules, list) or not rules:
        return ""
    lines = "\n".join(f"- {rule}" for rule in rules if str(rule).strip())
    return f"\n\nSafety rules:\n{lines}" if lines else ""


def normalize_history(conversation_history: list[dict[str, Any]], *, limit: int = 24) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in conversation_history[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            out.append({"role": role, "content": content})
    return out


def last_assistant_message(conversation_history: list[dict[str, Any]]) -> str:
    for item in reversed(normalize_history(conversation_history)):
        if item["role"] == "assistant":
            return item["content"]
    return ""


def last_assistant_before_last_user(conversation_history: list[dict[str, Any]]) -> str:
    norm = normalize_history(conversation_history)
    if norm and norm[-1]["role"] == "user":
        norm = norm[:-1]
    for item in reversed(norm):
        if item["role"] == "assistant":
            return item["content"]
    return ""


def _progress_block(
    *,
    answered_index: int,
    total: int,
    next_prompt: dict[str, Any] | None,
) -> str:
    lines = [f"\n\nInterview progress: {answered_index}/{total} topics covered."]
    if next_prompt:
        lines.append(
            "Next topic to explore "
            f"({next_prompt.get('id', '')} / {next_prompt.get('category', '')}): "
            f"{next_prompt.get('text', '')}"
        )
    return "\n".join(lines)


def build_interview_messages(
    *,
    system: str,
    conversation_history: list[dict[str, Any]],
    steering: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(normalize_history(conversation_history))
    messages.append({"role": "user", "content": steering})
    return messages


async def _stream_llm(brain: Any, messages: list[dict[str, Any]]) -> str:
    logger.debug(
        "interview_llm messages=%d roles=%s",
        len(messages),
        [m.get("role") for m in messages],
    )
    parts: list[str] = []
    async for chunk in brain.stream_chat(messages):
        parts.append(chunk)
    return "".join(parts).strip()


async def generate_interview_start(
    brain: Any,
    *,
    profile_id: str,
    modeled_user_alias: str,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    skill = _load_interview_skill(registry)
    prompts = _prompt_items(skill)
    if not prompts:
        raise ValueError("interview_skill_missing_prompts")
    first = prompts[0]
    system = INTERVIEW_SYSTEM_PROMPT + _safety_block(skill) + _progress_block(
        answered_index=0,
        total=len(prompts),
        next_prompt=first,
    )
    alias_note = f"Participant alias: {modeled_user_alias}." if modeled_user_alias.strip() else ""
    user_boot = (
        f"[START_INTERVIEW profile_id={profile_id}. {alias_note}]\n"
        "Welcome the participant briefly in a warm, natural tone. "
        "Remind them they may skip any question. "
        "Then ask your first question inspired by the next topic (do not read it verbatim)."
    )
    message = await _stream_llm(
        brain,
        build_interview_messages(system=system, conversation_history=[], steering=user_boot),
    )
    logger.info("interview_start profile=%s total_prompts=%d", profile_id, len(prompts))
    return {
        "message": message,
        "prompt_index": 0,
        "total_prompts": len(prompts),
        "complete": False,
        "samples": [],
    }


async def generate_interview_turn(
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
    skill = _load_interview_skill(registry)
    prompts = _prompt_items(skill)
    if not prompts:
        raise ValueError("interview_skill_missing_prompts")
    if prompt_index < 0 or prompt_index >= len(prompts):
        raise ValueError("invalid_prompt_index")

    history = conversation_history or []
    current = prompts[prompt_index]
    updated_samples = list(samples)
    sample_saved = False
    asked_prompt = last_assistant_before_last_user(history) or str(current.get("text", ""))

    if not skip and user_message.strip():
        updated_samples.append(
            {
                "prompt_id": str(current.get("id", "")),
                "category": str(current.get("category", "")),
                "prompt": asked_prompt,
                "response": user_message.strip(),
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

    message = await _stream_llm(
        brain,
        build_interview_messages(system=system, conversation_history=history, steering=steering),
    )
    logger.info(
        "interview_turn profile=%s index=%d->%d history=%d skip=%s samples=%d",
        profile_id,
        prompt_index,
        next_index,
        len(normalize_history(history)),
        skip,
        len(updated_samples),
    )
    return {
        "message": message,
        "prompt_index": next_index,
        "total_prompts": len(prompts),
        "complete": complete,
        "samples": updated_samples,
        "sample_saved": sample_saved,
    }


def build_raw_profile_payload(
    *,
    profile_id: str,
    modeled_user_alias: str,
    samples: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]] | None = None,
    registry: SkillRegistry | None = None,
) -> dict[str, Any]:
    skill = _load_interview_skill(registry)
    payload: dict[str, Any] = {
        "profile_id": profile_id,
        "modeled_user_alias": modeled_user_alias,
        "created_at": _utc_now_iso(),
        "consent_confirmed": True,
        "samples": samples,
        "post_processing_targets": skill.get("post_processing_targets") or [],
    }
    if conversation_history:
        payload["interview_transcript"] = normalize_history(conversation_history, limit=100)
    return payload
