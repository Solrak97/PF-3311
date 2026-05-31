"""Verify LangGraph profile workflow modules compile and graphs build."""

from __future__ import annotations

from app.agents.profile_state import default_training_state
from app.agents.refinement_graph import _build_feedback_graph
from app.agents.training_graph import _build_answer_graph, _build_finalize_graph
from app.agents.validation_graph import _build_finalize_validation_graph
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import default_profile_template, dump_profile_yaml, parse_profile_yaml


class _FakeBrain:
    async def stream_chat(self, messages):
        yield "mock"


def main() -> None:
    brain = _FakeBrain()
    import tempfile

    store = ProfileStore(base_dir=tempfile.mkdtemp())
    assert _build_answer_graph(brain) is not None
    assert _build_finalize_graph(brain, store) is not None
    assert _build_feedback_graph(brain, store) is not None
    assert _build_finalize_validation_graph(store) is not None
    tpl = default_profile_template("test-profile")
    roundtrip = parse_profile_yaml(dump_profile_yaml(tpl))
    assert roundtrip["profile_id"] == "test-profile"
    state = default_training_state("demo")
    assert state["status"] == "collecting"
    print("profile workflow smoke ok")


if __name__ == "__main__":
    main()
