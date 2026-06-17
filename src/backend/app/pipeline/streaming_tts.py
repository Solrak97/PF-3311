"""Incremental sentence extraction for streaming TTS during LLM output."""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r'[.!?…]+["\'\)]?\s*$')


def peel_complete_sentences(buffer: str) -> tuple[list[str], str]:
    """Return finished sentences and the trailing incomplete fragment."""
    text = buffer
    if not text.strip():
        return [], ""
    sentences: list[str] = []
    while True:
        match = re.search(r'(?<=[.!?…])["\'\)]?\s+', text)
        if not match:
            break
        chunk = text[: match.start() + 1].strip()
        # Include closing quote/paren attached to punctuation.
        end = match.start() + 1
        while end < match.end() and text[end] in "\"')":
            end += 1
        chunk = text[:end].strip()
        if chunk:
            sentences.append(chunk)
        text = text[match.end() :].lstrip()
    return sentences, text


def flush_remainder(remainder: str, *, min_chars: int = 4) -> list[str]:
    """Emit trailing text at end of turn."""
    tail = remainder.strip()
    if not tail:
        return []
    if len(tail) >= min_chars or _SENTENCE_END.search(tail):
        return [tail]
    return []
