"""Verify LangGraph agent graphs compile and context assembly works."""

from __future__ import annotations

from app.agents.conversation_agent import _build_context_graph, _build_conversation_graph
from app.agents.training_agent import _build_finalize_graph
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader


class _FakeBrain:
    async def stream_chat(self, messages):
        yield "mock reply"


def main() -> None:
    brain = _FakeBrain()
    store = ProfileStore()
    skills = SkillLoader()
    assert _build_context_graph(store, skills) is not None
    assert _build_conversation_graph(brain, store, skills) is not None
    assert _build_finalize_graph(brain, store, skills) is not None
    assert skills.get("train_profile").skill_id == "train_profile"
    assert skills.get("converse_with_profile").skill_id == "converse_with_profile"
    print("langgraph agents smoke ok")


if __name__ == "__main__":
    main()
