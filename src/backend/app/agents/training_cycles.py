from __future__ import annotations

from typing import Any

from app.agents.training_prompts import CORE_TRAINING_PROMPTS

CYCLE_PLANS: list[dict[str, Any]] = [
    {
        "target": "routine_register",
        "label": "Rutina y tono cotidiano",
        "prompt_ids": ["daily_routine", "after_work", "current_interest"],
    },
    {
        "target": "emotional_reaction",
        "label": "Reacciones emocionales",
        "prompt_ids": ["good_news", "annoying_situation", "boring_tasks"],
    },
    {
        "target": "banter_advice",
        "label": "Conversación y consejo",
        "prompt_ids": ["banter", "advice", "explain_to_friend"],
    },
    {
        "target": "discourse",
        "label": "Cierres y despedidas",
        "prompt_ids": ["closing", "banter"],
    },
]

PROBES_PER_CYCLE = 3
MIN_CYCLES_TO_FINISH = 2
MAX_REFINE_ROUNDS = 5


def prompt_by_id(prompt_id: str) -> dict[str, str]:
    for item in CORE_TRAINING_PROMPTS:
        if item.get("id") == prompt_id:
            return item
    return {"id": prompt_id, "category": "open", "text": prompt_id}


def cycle_plan(cycle_index: int) -> dict[str, Any]:
    if not CYCLE_PLANS:
        raise ValueError("no_cycle_plans")
    return CYCLE_PLANS[cycle_index % len(CYCLE_PLANS)]


def cycle_probe_ids(plan: dict[str, Any]) -> list[str]:
    ids = list(plan.get("prompt_ids") or [])
    return ids[:PROBES_PER_CYCLE]
