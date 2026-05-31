"""Verify interview message building includes conversation history."""

from __future__ import annotations

from app.experiment.interview import (
    build_interview_messages,
    last_assistant_before_last_user,
    normalize_history,
)


def main() -> None:
    history = [
        {"role": "assistant", "content": "Hola, ¿cómo fue tu día?"},
        {"role": "user", "content": "Bien, trabajé mucho."},
    ]
    norm = normalize_history(history)
    assert len(norm) == 2
    assert last_assistant_before_last_user(history) == "Hola, ¿cómo fue tu día?"

    messages = build_interview_messages(
        system="system",
        conversation_history=history,
        steering="[INTERVIEWER_TURN 2/10] acknowledge and ask next",
    )
    assert messages[0]["role"] == "system"
    assert messages[1]["content"] == history[0]["content"]
    assert messages[2]["content"] == history[1]["content"]
    assert messages[-1]["role"] == "user"
    assert "INTERVIEWER_TURN" in messages[-1]["content"]
    print("interview context smoke ok")


if __name__ == "__main__":
    main()
