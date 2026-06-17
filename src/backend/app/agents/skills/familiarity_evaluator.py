from __future__ import annotations

import json
import os
import re
from typing import Any

from app.agents.ai_judge import judge_profile_response, parse_judge_scores
from app.agents.rating_keys import BEHAVIORAL_PLAN_MATCH_KEY
from app.agents.brain_adapter import complete_chat
from app.config import settings
from app.prompts.renderer import render_template
from app.profiles.yaml_profile import dump_profile_yaml, merge_constraints
from app.skills.loader import SkillLoader

AI_JUDGE_SKILL_ID = "ai_judge"
_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

async def evaluate_plan_match(
    brain: Any,
    *,
    plan: dict[str, Any],
    agent_response: str,
    profile: dict[str, Any],
) -> float:
    """Score 0-10 whether response follows the behavioral plan."""
    prompt = render_template(
        "familiarity_plan_match",
        plan_json=json.dumps(plan, ensure_ascii=False),
        agent_response=agent_response.strip(),
        profile_yaml=dump_profile_yaml(merge_constraints(profile)) if profile.get("style") else "",
    )
    messages = [
        {"role": "system", "content": "You output JSON only."},
        {"role": "user", "content": prompt},
    ]
    raw = await complete_chat(brain, messages, num_predict=settings.llm_num_predict_json)
    cleaned = raw.strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
        score = float(data.get("score", data.get("behavioral_plan_match", 5)))
        return max(0.0, min(10.0, score))
    except (json.JSONDecodeError, TypeError, ValueError):
        return 5.0


async def evaluate_familiarity(
    brain: Any,
    *,
    profile: dict[str, Any],
    prompt: str,
    agent_response: str,
    plan: dict[str, Any] | None = None,
    skills: SkillLoader | None = None,
) -> dict[str, Any]:
    """Skill 7: offline + optional runtime familiarity evaluation."""
    registry = skills or SkillLoader()
    judged = await judge_profile_response(
        brain,
        profile=profile,
        prompt=prompt,
        agent_response=agent_response,
        skills=registry,
    )
    plan_score = None
    if plan:
        plan_score = await evaluate_plan_match(
            brain,
            plan=plan,
            agent_response=agent_response,
            profile=profile,
        )
        judged["scores"][BEHAVIORAL_PLAN_MATCH_KEY] = plan_score
    judged["plan_match_score"] = plan_score
    return judged


def runtime_regen_enabled() -> bool:
    return os.environ.get("RUNTIME_FAMILIARITY_REGEN", "0").strip().lower() in {"1", "true", "yes"}


def should_regenerate(eval_result: dict[str, Any], *, threshold: float = 6.0) -> bool:
    plan_score = eval_result.get("plan_match_score")
    if plan_score is not None and float(plan_score) < threshold:
        return True
    scores = eval_result.get("scores") or {}
    reminds = float(scores.get("reminds_me_of_person", 7))
    phrasing = float(scores.get("phrasing_similarity", 7))
    if reminds < 4.0 or phrasing < 4.0:
        return True
    return False


def parse_extended_judge_scores(raw: str, *, min_score: int = 1, max_score: int = 7) -> dict[str, Any]:
    from app.agents.rating_keys import RATING_KEYS

    parsed = parse_judge_scores(raw, min_score=min_score, max_score=max_score)
    cleaned = raw.strip()
    fence = _JSON_FENCE.search(cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(cleaned[start : end + 1])
            if BEHAVIORAL_PLAN_MATCH_KEY in data:
                parsed["scores"][BEHAVIORAL_PLAN_MATCH_KEY] = float(data[BEHAVIORAL_PLAN_MATCH_KEY])
        except json.JSONDecodeError:
            pass
    for key in RATING_KEYS:
        parsed["scores"].setdefault(key, 4.0)
    return parsed
