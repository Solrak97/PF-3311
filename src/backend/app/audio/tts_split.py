import re

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")


def split_for_tts(text: str, max_chars: int) -> list[str]:
    """Split spoken text into Edge-TTS-sized segments."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    segments: list[str] = []
    buf = ""
    for part in _SENTENCE_BREAK.split(text):
        part = part.strip()
        if not part:
            continue
        candidate = f"{buf} {part}".strip() if buf else part
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            segments.append(buf)
            buf = ""
        if len(part) <= max_chars:
            buf = part
            continue
        start = 0
        while start < len(part):
            segments.append(part[start : start + max_chars])
            start += max_chars
    if buf:
        segments.append(buf)
    return segments
