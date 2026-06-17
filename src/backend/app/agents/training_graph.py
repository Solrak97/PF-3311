"""Backward-compatible exports — use training_agent directly in new code."""

from app.agents.training_agent import (
    run_training_answer,
    run_training_finalize,
    run_training_finish,
    run_training_start,
    run_training_verdict,
)

__all__ = [
    "run_training_answer",
    "run_training_finalize",
    "run_training_finish",
    "run_training_start",
    "run_training_verdict",
]
