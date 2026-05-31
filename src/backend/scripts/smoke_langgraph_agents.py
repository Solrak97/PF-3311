"""Verify LangGraph agent graphs compile and context assembly works."""

from __future__ import annotations

from app.agents.chat_graph import _build_context_graph
from app.agents.interview_graph import _build_start_graph, _build_turn_graph
from app.experiment.interview import build_interview_messages, normalize_history
from app.profiles.store import ProfileStore
from app.skills.registry import SkillRegistry


class _FakeBrain:
    async def stream_chat(self, messages):
        yield "mock reply"


def main() -> None:
    brain = _FakeBrain()
    assert _build_start_graph(brain) is not None
    assert _build_turn_graph(brain) is not None
    assert _build_context_graph() is not None

    history = [
        {"role": "assistant", "content": "Hola"},
        {"role": "user", "content": "Bien"},
    ]
    messages = build_interview_messages(
        system="system",
        conversation_history=history,
        steering="[NEXT]",
    )
    assert len(messages) == 4

    store = ProfileStore()
    skills = SkillRegistry()
    print("langgraph agents smoke ok")


if __name__ == "__main__":
    main()
