"""Smoke test for generic_control_agent control profile."""

from __future__ import annotations

from app.experiment.chat import build_system_prompt, resolved_profile_id
from app.profiles.control import CONTROL_PROFILE_ID, build_control_system_prompt, load_control_profile
from app.profiles.store import ProfileStore
from app.skills.registry import SkillRegistry
from pathlib import Path
import tempfile


def main() -> None:
    profile = load_control_profile()
    assert profile["profile_id"] == CONTROL_PROFILE_ID
    prompt = build_control_system_prompt(profile)
    assert "Condition B control baseline" in prompt
    assert "familiarity" in prompt.lower() or "Familiarity" in prompt or "familiar" in prompt.lower()

    td = tempfile.mkdtemp()
    store = ProfileStore(Path(td))
    raw = {
        "profile_id": "trained-a",
        "samples": [{"prompt": "hola", "response": "que tal amigo"}],
        "consent_confirmed": True,
    }
    from app.profiles.builder import compile_behavioral

    store.save_behavioral(compile_behavioral(raw))

    b_prompt, b_used, b_ret, _b_scenario = build_system_prompt(
        condition="B",
        profile_store=store,
        profile_id="trained-a",
        user_message="hola",
        skills=SkillRegistry(),
    )
    assert b_used and not b_ret
    assert _b_scenario == "daily_conversation"
    assert "Current scenario" in b_prompt
    assert "Experimental constraints" in b_prompt
    assert "que tal amigo" not in b_prompt

    a_prompt, a_used, _a_ret, a_scenario = build_system_prompt(
        condition="A",
        profile_store=store,
        profile_id="trained-a",
        user_message="hola",
        skills=SkillRegistry(),
    )
    assert a_used
    assert a_scenario == "daily_conversation"
    assert "Current scenario" in a_prompt
    assert "Behavioral style" in a_prompt

    assert resolved_profile_id(condition="B", profile_id="anything") == CONTROL_PROFILE_ID
    print("control profile smoke ok")


if __name__ == "__main__":
    main()
