#!/usr/bin/env python3
"""Generate a synthetic SQLite DB with 5 complete pilot participants for pipeline testing."""

from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

BACKEND_ROOT = ANALYSIS_DIR.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.storage.sqlite_store import SQLiteExperimentStore, TurnRecord  # noqa: E402
from mappings import COMPOSITE_GROUPS  # noqa: E402


def _likert(mu_a: float, mu_b: float, spread: float = 1.2) -> tuple[dict[str, float], dict[str, float]]:
    """Build item-level responses around composite means."""
    resp_a: dict[str, float] = {}
    resp_b: dict[str, float] = {}
    for composite, keys in COMPOSITE_GROUPS.items():
        va = max(1, min(7, random.gauss(mu_a, spread)))
        vb = max(1, min(7, random.gauss(mu_b, spread)))
        for key in keys:
            scale = 9 if key.startswith("sam_") else 7 if not key.startswith("gs_") else 5
            resp_a[key] = round(max(1, min(scale, va + random.gauss(0, 0.6))), 0)
            resp_b[key] = round(max(1, min(scale, vb + random.gauss(0, 0.6))), 0)
    return resp_a, resp_b


def populate_demo_db(db_path: Path, n_participants: int = 5, seed: int = 42) -> None:
    random.seed(seed)
    store = SQLiteExperimentStore(str(db_path))

    for i in range(1, n_participants + 1):
        pid = f"P{i:02d}"
        order = "A-B" if i % 2 else "B-A"
        run_id = f"demo-exp-{i:04d}"
        cond_order = order.split("-")

        for interaction_idx, cond in enumerate(cond_order, start=1):
            sid = f"{run_id}-i{interaction_idx}"
            n_turns = random.randint(4, 12)
            for t in range(1, n_turns + 1):
                store.insert_turn(
                    TurnRecord(
                        participant_id=pid,
                        session_id=sid,
                        condition=cond,
                        order_group=order,
                        turn_index=t,
                        user_text=f"[{pid}] mensaje usuario turno {t}",
                        assistant_text=f"respuesta agente cond {cond} turno {t}",
                        profile_used=cond == "A",
                        retrieval_used=cond == "A" and random.random() > 0.3,
                        model_name="demo-model",
                        audio_error_count=0,
                        created_at=f"2026-06-10T12:{interaction_idx:02d}:{t:02d}:00+00:00",
                        profile_id="demo_profile" if cond == "A" else "generic_control_agent",
                        interaction_index=interaction_idx,
                        scenario_id="daily_conversation",
                    )
                )
            store.record_session_end(
                session_id=sid,
                duration_sec=random.randint(180, 320),
                participant_id=pid,
                condition=cond,
                order_group=order,
                end_reason="timer",
            )

        resp_a, resp_b = _likert(mu_a=5.2, mu_b=3.6)
        for interaction_idx, cond in enumerate(cond_order, start=1):
            sid = f"{run_id}-i{interaction_idx}"
            responses = resp_a if cond == "A" else resp_b
            store.insert_questionnaire_response(
                run_session_id=run_id,
                session_id=sid,
                participant_id=pid,
                condition=cond,
                order_group=order,
                interaction_index=interaction_idx,
                questionnaire_after_interaction=interaction_idx,
                profile_id="demo_profile" if cond == "A" else "generic_control_agent",
                scenario_id="daily_conversation",
                responses=responses,
            )


def main() -> int:
    out = ANALYSIS_DIR / "exports" / "demo_synthetic"
    out.mkdir(parents=True, exist_ok=True)
    db_path = out / "experiment_demo.db"
    if db_path.is_file():
        db_path.unlink()
    populate_demo_db(db_path, n_participants=5)
    print(f"Demo DB: {db_path}")
    print("Run analysis with:")
    print(f"  python run_pilot_analysis.py --db {db_path} --out {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
