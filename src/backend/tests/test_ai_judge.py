from app.agents.ai_judge import parse_judge_scores


def test_parse_judge_scores_plain_json() -> None:
    raw = """{
        "tone_similarity": 5,
        "phrasing_similarity": 6,
        "response_length_similarity": 4,
        "behavioral_consistency": 5,
        "reminds_me_of_person": 4,
        "naturalness": 6,
        "identity_leakage_absent": 7,
        "rationale": "Bien."
    }"""
    result = parse_judge_scores(raw)
    assert result["scores"]["naturalness"] == 6.0
    assert result["scores"]["identity_leakage_absent"] == 7.0
    assert result["rationale"] == "Bien."


def test_parse_judge_scores_fenced_json() -> None:
    raw = """Here are the scores:
```json
{"tone_similarity": 3, "phrasing_similarity": 3, "response_length_similarity": 3,
 "behavioral_consistency": 3, "reminds_me_of_person": 2, "naturalness": 4,
 "identity_leakage_absent": 6, "rationale": "ok"}
```"""
    result = parse_judge_scores(raw)
    assert result["scores"]["tone_similarity"] == 3.0


def test_parse_judge_scores_clamps() -> None:
    raw = '{"tone_similarity": 99, "phrasing_similarity": 0, "response_length_similarity": 4, "behavioral_consistency": 4, "reminds_me_of_person": 4, "naturalness": 4, "identity_leakage_absent": 4}'
    result = parse_judge_scores(raw)
    assert result["scores"]["tone_similarity"] == 7.0
    assert result["scores"]["phrasing_similarity"] == 1.0
