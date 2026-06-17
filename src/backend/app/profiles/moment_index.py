from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.agents.profile_state import BehavioralProfileState
from app.brain.embeddings import embed_text
from app.profiles.store import ProfileStore


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _moment_summary(prompt: str, response: str) -> str:
    p = prompt.strip()[:120]
    r = response.strip()[:160]
    return f"Asked about: {p}. Responded: {r}"


def build_moments_from_state(state: BehavioralProfileState) -> list[dict[str, Any]]:
    moments: list[dict[str, Any]] = []
    turn = 0
    for sample in state.get("raw_samples") or []:
        if not isinstance(sample, dict):
            continue
        response = str(sample.get("response", "")).strip()
        if not response or response == "[skipped]":
            continue
        turn += 1
        situation = str(sample.get("category") or "open")
        prompt = str(sample.get("prompt", ""))
        exemplar = str(sample.get("mirror_attempt") or response)
        moments.append(
            {
                "id": f"m-{turn:03d}",
                "situation": situation,
                "summary": _moment_summary(prompt, response),
                "exemplar_line": exemplar[:300],
                "prompt": prompt[:300],
                "response": response[:300],
                "source_turn": turn,
                "verdict": sample.get("verdict", ""),
            }
        )
    for cycle in state.get("cycles_completed") or []:
        if not isinstance(cycle, dict):
            continue
        accepted = str(cycle.get("accepted_imitation", "")).strip()
        if not accepted:
            continue
        turn += 1
        moments.append(
            {
                "id": f"m-mirror-{turn:03d}",
                "situation": str(cycle.get("signal_target") or "mirror_calibration"),
                "summary": f"Accepted mirror imitation in {cycle.get('label', 'calibration')}",
                "exemplar_line": accepted[:300],
                "prompt": "",
                "response": accepted[:300],
                "source_turn": turn,
                "verdict": "accept",
            }
        )
    return moments


async def build_and_save_moment_index(
    brain: Any,
    store: ProfileStore,
    profile_id: str,
    state: BehavioralProfileState,
) -> dict[str, Any]:
    """Build retrievable moment index with optional embeddings."""
    moments = build_moments_from_state(state)
    for moment in moments:
        embed_input = f"{moment.get('situation', '')} {moment.get('summary', '')}"
        embedding = await embed_text(embed_input)
        if embedding:
            moment["embedding"] = embedding
    payload = {
        "profile_id": profile_id,
        "created_at": _utc_now(),
        "moments": moments,
        "moment_count": len(moments),
    }
    return store.save_moments(payload)


def new_moment_id() -> str:
    return f"m-{uuid.uuid4().hex[:8]}"
