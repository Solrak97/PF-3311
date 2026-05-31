"""Open-ended training: mirror turns and user-controlled finish."""

from __future__ import annotations

import asyncio
import tempfile

from app.agents.training_graph import (
    MIN_SAMPLES_TO_FINISH,
    MIRROR_EVERY_N_SAMPLES,
    run_training_answer,
    run_training_finish,
    run_training_start,
)
from app.profiles.store import ProfileStore


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
    brain = _ScriptedBrain(
        [
            "Hola — conversación abierta. ¿Cómo va tu día?",  # start
            "¿Qué haces después del trabajo?",  # answer 1
            "Ahora voy a tratar de imitarte y me dices qué te parece.\n\n"
            "Imagina que te preguntan el clima.\n\n"
            "Yo diría algo como: «Ay, qué calor — preferiría quedarme en casa.»\n\n"
            "¿Es esto algo que dirías?",
            "¿Qué te gusta hacer el fin de semana?",  # after mirror feedback
            "Gracias — ya puedes guardar.",  # finish closing
        ]
    )
    pid = "pf-open"
    start = await run_training_start(brain, store, profile_id=pid, modeled_user_alias="Test")
    assert start["open_ended"] is True
    assert start["total_prompts"] == 0
    assert start["complete"] is False

    t1 = await run_training_answer(brain, store, profile_id=pid, user_message="Bien, ocupado.")
    assert t1["sample_count"] == 1
    assert t1["turn_mode"] == "interview"

    t2 = await run_training_answer(brain, store, profile_id=pid, user_message="Salgo a caminar.")
    assert t2["sample_count"] == 2
    assert t2["turn_mode"] == "mirror"
    assert store.load_session(pid, "training")["awaiting_mirror_feedback"] is True

    t3 = await run_training_answer(
        brain,
        store,
        profile_id=pid,
        user_message="Casi — diría más relajado.",
    )
    assert t3["sample_count"] == 3
    assert any(s.get("category") == "mirror_calibration" for s in t3["samples"])

    finished = await run_training_finish(brain, store, profile_id=pid)
    assert finished["complete"] is True
    assert finished["turn_mode"] == "finish"

    assert MIN_SAMPLES_TO_FINISH == 3
    assert MIRROR_EVERY_N_SAMPLES == 2


def main() -> None:
    asyncio.run(_run())
    print("smoke_open_training ok")


if __name__ == "__main__":
    main()
