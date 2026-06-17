"""Calibration cycle training: probe → imitate → verdict → next cycle."""

from __future__ import annotations

import asyncio
import tempfile

from app.agents.training_agent import (
    run_training_answer,
    run_training_finish,
    run_training_start,
    run_training_verdict,
)
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader

_calibration = SkillLoader().get("train_profile").calibration
MIN_CYCLES_TO_FINISH = int(_calibration.get("min_cycles_to_finish", 2))
PROBES_PER_CYCLE = int(_calibration.get("probes_per_cycle", 3))


class _ScriptedBrain:
    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self._idx = 0

    async def stream_chat(self, messages):
        text = self._replies[min(self._idx, len(self._replies) - 1)]
        self._idx += 1
        yield text


async def _run() -> None:
    store = ProfileStore(base_dir=tempfile.mkdtemp())
    replies = [
        "Hola — ciclo 1 pregunta 1. ¿Cómo fue tu día?",
        "¿Qué haces después del trabajo?",
        "¿Qué te gusta hacer últimamente?",
        "Imitación ciclo 1…",
        "Imitación refinada…",
        "Ciclo 2 pregunta 1…",
        "Ciclo 2 pregunta 2…",
        "Ciclo 2 pregunta 3…",
        "Imitación ciclo 2…",
        "Cierre — puedes guardar.",
    ]
    brain = _ScriptedBrain(replies)
    pid = "pf-cycle"

    start = await run_training_start(brain, store, profile_id=pid, modeled_user_alias="Test")
    assert start["calibration_cycles"] is True
    assert start["cycle_phase"] == "probe"
    assert start["probe_progress"] == "0/3"

    for answer in ("Bien", "Camino", "Leer"):
        result = await run_training_answer(brain, store, profile_id=pid, user_message=answer)
    assert result["awaiting_verdict"] is True
    assert result["turn_mode"] in {"mirror", "refine"}

    refined = await run_training_verdict(
        brain,
        store,
        profile_id=pid,
        verdict="refine",
        user_message="Suena muy formal.",
    )
    assert refined["awaiting_verdict"] is True

    accepted = await run_training_verdict(brain, store, profile_id=pid, verdict="accept")
    assert accepted["cycle_count"] == 1
    assert not accepted["awaiting_verdict"]

    for answer in ("Respuesta A", "Respuesta B", "Respuesta C"):
        await run_training_answer(brain, store, profile_id=pid, user_message=answer)
    await run_training_verdict(brain, store, profile_id=pid, verdict="accept")

    state = store.load_session(pid, "training")
    assert state is not None
    assert len(state.get("cycles_completed") or []) == 2

    finished = await run_training_finish(brain, store, profile_id=pid)
    assert finished["complete"] is True
    assert MIN_CYCLES_TO_FINISH == 2
    assert PROBES_PER_CYCLE == 3


def main() -> None:
    asyncio.run(_run())
    print("smoke_calibration_cycles ok")


if __name__ == "__main__":
    main()
