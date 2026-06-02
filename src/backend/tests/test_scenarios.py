from app.experiment.scenario_prompt import CONVERSATION_OPEN_CUE, compose_experiment_system_prompt
from app.experiment.scenarios import DEFAULT_SCENARIO_ID, get_scenario, resolve_scenario_id
from app.experiment.chat import build_system_prompt
from app.profiles.store import ProfileStore
from app.skills.registry import SkillRegistry
from pathlib import Path
import tempfile


def test_resolve_scenario_defaults() -> None:
    assert resolve_scenario_id(None) == DEFAULT_SCENARIO_ID
    assert resolve_scenario_id("") == DEFAULT_SCENARIO_ID
    assert resolve_scenario_id("unknown") == DEFAULT_SCENARIO_ID
    assert resolve_scenario_id("casual_support") == "casual_support"


def test_compose_includes_layers() -> None:
    scenario = get_scenario("daily_conversation")
    system = compose_experiment_system_prompt(
        scenario=scenario,
        profile_style="Warm, informal Spanish.",
    )
    assert "Current scenario" in system
    assert "Conversación cotidiana guiada" in system
    assert "Behavioral style" in system
    assert "Experimental constraints" in system
    assert "Warm, informal Spanish." in system


def test_conversation_open_cue_present() -> None:
    cue = CONVERSATION_OPEN_CUE.lower()
    assert "conversación acaba de empezar" in cue
    assert "buddy" in cue
    assert "mujer" in cue


def test_condition_b_skips_retrieval() -> None:
    td = tempfile.mkdtemp()
    store = ProfileStore(Path(td))
    prompt, used, retrieval, scenario = build_system_prompt(
        condition="B",
        profile_store=store,
        profile_id="any",
        user_message="hola",
        skills=SkillRegistry(),
        scenario_id="daily_conversation",
    )
    assert used
    assert not retrieval
    assert scenario == "daily_conversation"
    assert "Current scenario" in prompt


if __name__ == "__main__":
    import unittest

    unittest.main()
