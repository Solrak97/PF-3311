"""Run a continuous calibration training session and finalize to behavioral YAML."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from app.agents.training_agent import (
    run_training_answer,
    run_training_finalize,
    run_training_finish,
    run_training_start,
    run_training_verdict,
)
from app.brain.factory import create_brain
from app.config import settings
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader

# Scripted Spanish answers (sassy casual register) for automated dev training.
SCRIPTED_ANSWERS: list[str] = [
    "Ay, qué sorpresa, otro día. Fatal, como siempre — trabajo, tráfico y ya en casa.",
    "Lo de siempre: música y sillón. Recompensa por no mandar a todos al carajo.",
    "Cocino cosas sencillas y me quejo de que nadie lava los platos. Qué romántico, ¿no?",
    "¡Ay, qué bien! Me alegro… seguro después viene algo malo para equilibrar el universo.",
    "Uf, qué fastidio. No es el fin del mundo… aunque en el momento sí parece.",
    "Jaja, ok, no está mal. Podría ser peor.",
    "Bueno, me voy. No me ignores demasiado, ¿eh? Besito.",
]


async def _train(
    profile_id: str,
    modeled_user_alias: str,
    *,
    accept_imitation: bool = True,
    max_turns: int = 12,
) -> dict:
    store = ProfileStore(settings.profiles_data_dir)
    brain = create_brain()
    calibration = SkillLoader().get("train_profile").calibration

    start = await run_training_start(
        brain,
        store,
        profile_id=profile_id,
        modeled_user_alias=modeled_user_alias,
    )
    print(f"[start] {start.get('message', '')[:140]}...")

    answer_idx = 0
    for turn in range(max_turns):
        state = store.load_session(profile_id, "training") or {}
        if state.get("complete"):
            break
        if state.get("awaiting_verdict"):
            verdict = "accept" if accept_imitation else "refine"
            correction = "" if accept_imitation else "Suena un poco más relajado y menos formal."
            result = await run_training_verdict(
                brain,
                store,
                profile_id=profile_id,
                verdict=verdict,
                user_message=correction,
            )
            print(
                f"[verdict] {verdict} mirrors={result.get('mirror_count')} "
                f"mode={result.get('turn_mode')}"
            )
            continue

        if answer_idx >= len(SCRIPTED_ANSWERS):
            break
        answer = SCRIPTED_ANSWERS[answer_idx]
        answer_idx += 1
        result = await run_training_answer(
            brain,
            store,
            profile_id=profile_id,
            user_message=answer,
        )
        print(
            f"[answer] turn={turn + 1} mode={result.get('turn_mode')} "
            f"progress={result.get('probe_progress')} "
            f"draft={bool(result.get('profile_draft_ready'))}"
        )

    finished = await run_training_finish(brain, store, profile_id=profile_id)
    print(f"[finish] complete={finished.get('complete')}")

    saved = await run_training_finalize(brain, store, profile_id=profile_id)
    return saved


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Train a behavioral profile end-to-end")
    parser.add_argument("--profile-id", default="", help="Profile id (default: pf-YYYYMMDD-HHMM)")
    parser.add_argument("--alias", default="Participante", help="Modeled user alias")
    parser.add_argument("--turns", type=int, default=12, help="Max automated turns")
    args = parser.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    profile_id = args.profile_id.strip() or f"pf-{stamp}"

    try:
        result = await _train(profile_id, args.alias.strip(), max_turns=max(1, args.turns))
    except Exception as exc:  # noqa: BLE001
        print(f"training failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(
        {
            "ok": result.get("ok"),
            "profile_id": result.get("profile_id"),
            "status": result.get("status"),
            "sample_count": result.get("sample_count"),
            "cycles_completed": result.get("cycles_completed"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
