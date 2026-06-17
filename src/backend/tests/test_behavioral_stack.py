from __future__ import annotations

from app.agents.skills.behavioral_observer import merge_observation_into_situation_modes
from app.agents.skills.behavioral_planner import build_heuristic_plan
from app.agents.skills.situation_classifier import _keyword_classify
from app.brain.embeddings import cosine_similarity
from app.profiles.yaml_profile import normalize_profile_yaml, sanitize_grounded_phrases


def test_sanitize_grounded_phrases_removes_dict_strings() -> None:
    profile = normalize_profile_yaml(
        {
            "profile_id": "test",
            "lexical_patterns": {
                "common_phrases": [
                    "hola amor",
                    "{'line': 'bad nested'}",
                    "{context: daily, line: corrupt}",
                ],
            },
        }
    )
    cleaned = sanitize_grounded_phrases(profile)
    phrases = cleaned["lexical_patterns"]["common_phrases"]
    assert "hola amor" in phrases
    assert not any("{" in p for p in phrases)


def test_situation_modes_merge() -> None:
    profile = normalize_profile_yaml({"profile_id": "test"})
    observation = {
        "situation_hint": "banter_advice",
        "reasoning_style": ["practical"],
        "conversational_habits": ["asks questions first"],
    }
    merged = merge_observation_into_situation_modes(profile, observation)
    modes = merged["situation_modes"]
    assert "banter_advice" in modes
    assert "practical" in modes["banter_advice"]["traits"]


def test_keyword_classify_emotional() -> None:
    situation, conf = _keyword_classify("Hoy me siento triste y preocupado")
    assert situation == "emotional_reaction"
    assert conf > 0.2


def test_cosine_similarity() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_heuristic_plan_from_situation_modes() -> None:
    profile = normalize_profile_yaml(
        {
            "profile_id": "test",
            "style": {"formality": "informal"},
            "situation_modes": {
                "routine_register": {
                    "traits": ["complains playfully"],
                    "response_strategy": ["mirror boredom"],
                }
            },
            "response_structure": {"default_pattern": ["Ay…", "short answer"]},
        }
    )
    plan = build_heuristic_plan(profile, "routine_register")
    assert "complains playfully" in plan["behaviors"]
    assert "mirror boredom" in plan["response_strategy"]
    assert "Ay…" in plan["structure"]
