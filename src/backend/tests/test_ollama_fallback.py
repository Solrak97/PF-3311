from __future__ import annotations

from app.brain.fallback import FallbackOllamaBrain


def test_fallback_brain_retryable_errors() -> None:
    import httpx

    assert FallbackOllamaBrain._is_retryable(TimeoutError("x"))
    assert FallbackOllamaBrain._is_retryable(httpx.ConnectError("x"))
    assert not FallbackOllamaBrain._is_retryable(ValueError("x"))


if __name__ == "__main__":
    test_fallback_brain_retryable_errors()
    print("ok")
