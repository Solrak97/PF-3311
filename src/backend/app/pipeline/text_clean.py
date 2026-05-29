"""Strip roleplay stage directions from spoken/display text; map them to avatar clips."""

from __future__ import annotations

import re
from typing import Any

ASTERISK_ACTION = re.compile(r"\*[^*]+\*")
BRACKET_ACTION = re.compile(r"\[[^\]]+\]")
# Collapse whitespace left after removals.
_WS = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")
# Trailing incomplete *action or [direction while streaming.
_TRAIL_ASTERISK = re.compile(r"\*[^*]*$")
_TRAIL_BRACKET = re.compile(r"\[[^\]]*$")


def contains_roleplay_markers(text: str) -> bool:
    if not text:
        return False
    return bool(ASTERISK_ACTION.search(text) or BRACKET_ACTION.search(text))


def strip_roleplay_markers(text: str) -> str:
    """Remove *actions* and [stage directions] from user-visible and TTS text."""
    if not text:
        return ""
    out = text
    out = ASTERISK_ACTION.sub("", out)
    out = BRACKET_ACTION.sub("", out)
    out = _WS.sub(" ", out)
    out = _BLANK_LINES.sub("\n\n", out)
    return out.strip()


def strip_roleplay_for_stream(text: str) -> str:
    """Strip complete markers and hide a trailing partial * or [ until the token finishes."""
    out = strip_roleplay_markers(text)
    out = _TRAIL_ASTERISK.sub("", out)
    out = _TRAIL_BRACKET.sub("", out)
    return out.rstrip()


def extract_roleplay_animation_hints(text: str) -> list[dict[str, Any]]:
    """Turn roleplay markers into anim.command payloads (before they are stripped)."""
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pattern in (ASTERISK_ACTION, BRACKET_ACTION):
        for match in pattern.finditer(text):
            inner = match.group(0)
            if inner.startswith("*") and inner.endswith("*"):
                label = inner[1:-1].strip()
            elif inner.startswith("[") and inner.endswith("]"):
                label = inner[1:-1].strip()
            else:
                continue
            clip_id = _marker_to_clip_id(label)
            if clip_id is None or clip_id in seen:
                continue
            seen.add(clip_id)
            hints.append({"clip_id": clip_id, "blend_time": 0.25})
    return hints


def merge_animations(
    primary: list[dict[str, Any]], extra: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """JSON animations first, then roleplay-derived clips (no duplicate clip_id)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (primary, extra):
        for item in source:
            if not isinstance(item, dict):
                continue
            clip = str(item.get("clip_id", "")).strip().lower()
            if not clip or clip in seen:
                continue
            seen.add(clip)
            out.append(
                {
                    "clip_id": clip,
                    "blend_time": float(item.get("blend_time", 0.2)),
                }
            )
    return out


def _marker_to_clip_id(label: str) -> str | None:
    low = label.lower()
    if any(w in low for w in ("wave", "hello", "hi there", "greet")):
        return "wave"
    if any(w in low for w in ("nod", "nods", "agree", "yes")):
        return "nod"
    if any(
        w in low
        for w in (
            "think",
            "thinking",
            "ponder",
            "consider",
            "blush",
            "embarrass",
            "shy",
            "nervous",
        )
    ):
        return "think"
    if any(w in low for w in ("speak", "speaking", "talk", "say", "start")):
        return "nod"
    if any(w in low for w in ("idle", "wait", "listen", "pause")):
        return "idle"
    return None
