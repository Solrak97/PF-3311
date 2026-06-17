from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agents.brain_adapter import complete_chat
from app.agents.rating_keys import RATING_KEYS
from app.config import settings
from app.prompts.renderer import render_template
from app.profiles.yaml_profile import dump_profile_yaml, merge_constraints
from app.skills.loader import SkillLoader

logger = logging.getLogger(__name__)

AI_JUDGE_SKILL_ID = "ai_judge"
_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def _clamp_score(value: Any, *, min_score: int, max_score: int) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 4.0
    return float(max(min_score, min(max_score, int(round(numeric)))))


def parse_judge_scores(raw: str, *, min_score: int = 1, max_score: int = 7) -> dict[str, Any]:
    text = raw.strip()
    candidates = [text]
    fence = _JSON_FENCE.search(text)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])

    parsed: dict[str, Any] | None = None
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                parsed = data
                break
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
    if parsed is None:
        raise ValueError(f"judge_json_parse_failed: {last_error}")

    scores = {
        key: _clamp_score(parsed.get(key), min_score=min_score, max_score=max_score)
        for key in RATING_KEYS
    }
    return {
        "scores": scores,
        "rationale": str(parsed.get("rationale", "")).strip(),
    }


async def judge_profile_response(
    brain: Any,
    *,
    profile: dict[str, Any],
    prompt: str,
    agent_response: str,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    registry = skills or SkillLoader()
    skill = registry.get(AI_JUDGE_SKILL_ID)
    scale = skill.data.get("rating_scale") or {}
    min_score = int(scale.get("min", 1))
    max_score = int(scale.get("max", 7))
    validator_id = str(skill.get("validator_id", "ai-judge"))

    if profile.get("style"):
        profile_yaml = dump_profile_yaml(merge_constraints(profile))
    else:
        profile_yaml = str(profile.get("style_summary", "(no profile yaml)"))

    system = render_template(skill.templates.get("system", "ai_judge_system"))
    user_prompt = render_template(
        skill.templates.get("rating", "ai_judge_rating"),
        profile_yaml=profile_yaml,
        modeled_user_alias=str(profile.get("modeled_user_alias", "")),
        prompt=prompt.strip(),
        agent_response=agent_response.strip(),
        scale_min=min_score,
        scale_max=max_score,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]
    raw = await complete_chat(brain, messages, num_predict=settings.llm_num_predict_json)
    try:
        judged = parse_judge_scores(raw, min_score=min_score, max_score=max_score)
    except ValueError:
        logger.warning("ai_judge_parse_fallback validator=%s raw_len=%s", validator_id, len(raw))
        scores = {key: 4.0 for key in RATING_KEYS}
        for key in RATING_KEYS:
            match = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9.]+)', raw)
            if match:
                scores[key] = _clamp_score(match.group(1), min_score=min_score, max_score=max_score)
        judged = {
            "scores": scores,
            "rationale": raw.strip()[:500] or "judge returned non-JSON response",
        }
    logger.info(
        "ai_judge validator=%s naturalness=%.0f identity_safety=%.0f",
        validator_id,
        judged["scores"].get("naturalness", 0),
        judged["scores"].get("identity_leakage_absent", 0),
    )
    return {
        "validator_id": validator_id,
        "scores": judged["scores"],
        "rationale": judged["rationale"],
        "raw": raw,
    }
