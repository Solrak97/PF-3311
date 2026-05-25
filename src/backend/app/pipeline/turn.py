import asyncio
import json
import logging
import re
from typing import Any

from fastapi import WebSocket

from app.audio.tts import EdgeTtsEngine
from app.brain.ollama import OllamaBrain

logger = logging.getLogger(__name__)

JSON_BLOCK = re.compile(r"<JSON>\s*(\{.*?\})\s*</JSON>\s*$", re.DOTALL)
JSON_TAG = "<JSON>"
META_START = re.compile(r"\n\s*(?:<JSON|\{\s*\"animations\")")

SYSTEM_PROMPT = """You are Buddy, a friendly embodied assistant the user talks to in a 3D scene.
Keep answers concise and conversational (this will be spoken aloud). Prefer short paragraphs.
After your answer, append one final line exactly in this machine-readable format (tags required):
<JSON>{"animations":[{"clip_id":"idle","blend_time":0.2}]}</JSON>

clip_id must be one of: idle, nod, wave, think. Use one or two animations that fit the tone."""


def _spoken_and_animations(full: str) -> tuple[str, list[dict[str, Any]]]:
    text = _visible_cutoff(full.strip())
    m = JSON_BLOCK.search(full.strip())
    if not m:
        meta = META_START.search(full.strip())
        if meta:
            tail = full.strip()[meta.start() :]
            try:
                data = json.loads(tail.removeprefix("<JSON>").removesuffix("</JSON>").strip())
                anims = data.get("animations") if isinstance(data, dict) else []
                if isinstance(anims, list):
                    return text, [a for a in anims if isinstance(a, dict)]
            except json.JSONDecodeError:
                pass
        return text, []
    raw = m.group(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return text[: m.start()].strip(), []
    anims = data.get("animations")
    if not isinstance(anims, list):
        anims = []
    return text, [a for a in anims if isinstance(a, dict)]


def spoken_for_tts(full: str) -> str:
    spoken, _ = _spoken_and_animations(full)
    if spoken:
        return spoken
    stripped = JSON_BLOCK.sub("", full.strip()).strip()
    return stripped


def _visible_cutoff(full: str) -> str:
    """Hide machine-readable tail even if the model omits newlines or closing tags."""
    for marker in ("<JSON", '{"animations"', '{ "animations"'):
        pos = full.find(marker)
        if pos >= 0:
            return full[:pos].rstrip()
    m = META_START.search(full)
    if m:
        return full[: m.start()].rstrip()
    return full


def _visible_delta(full: str, sent_visible_len: int) -> tuple[str, int]:
    visible = _visible_cutoff(full)
    new_text = visible[sent_visible_len:]
    return new_text, len(visible)


async def send_event(ws: WebSocket, typ: str, payload: dict[str, Any]) -> None:
    await ws.send_text(json.dumps({"v": 1, "type": typ, "payload": payload}, ensure_ascii=False))


async def run_text_turn(ws: WebSocket, user_text: str, brain: OllamaBrain, tts: EdgeTtsEngine) -> None:
    await send_event(ws, "listening.state", {"state": "processing"})
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text.strip()},
    ]
    full = ""
    sent_visible_len = 0
    try:
        async for delta in brain.stream_chat(messages):
            full += delta
            chunk, sent_visible_len = _visible_delta(full, sent_visible_len)
            if chunk:
                await send_event(ws, "llm.delta", {"text": chunk})
            await asyncio.sleep(0)
    except Exception as exc:  # noqa: BLE001
        logger.exception("brain stream failed")
        await send_event(ws, "turn.end", {"error": str(exc)})
        return

    spoken, anims = _spoken_and_animations(full)
    display = spoken if spoken else spoken_for_tts(full)
    await send_event(ws, "llm.done", {"full_text": display})

    if anims:
        for item in anims:
            clip = str(item.get("clip_id", "idle"))
            blend = float(item.get("blend_time", 0.2))
            await send_event(ws, "anim.command", {"clip_id": clip, "blend_time": blend})
    else:
        await send_event(ws, "anim.command", {"clip_id": "idle", "blend_time": 0.2})

    tts_text = spoken_for_tts(full)
    audio_errors: list[str] = []
    if tts_text:
        try:
            segments = await tts.synthesize_mp3_segments(tts_text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("tts failed")
            await send_event(ws, "turn.end", {"error": f"tts: {exc}"})
            return

        total = len(segments)
        for index, mp3 in enumerate(segments):
            try:
                if not mp3:
                    raise ValueError("empty audio segment")
                await send_event(
                    ws,
                    "tts.chunk_meta",
                    {
                        "format": "mp3",
                        "index": index,
                        "total": total,
                        "final": index == total - 1,
                        "bytes": len(mp3),
                    },
                )
                await ws.send_bytes(mp3)
            except Exception as exc:  # noqa: BLE001
                logger.exception("tts chunk %s failed", index)
                audio_errors.append(str(exc))
                await send_event(
                    ws,
                    "tts.error",
                    {"index": index, "total": total, "error": str(exc)},
                )
            await asyncio.sleep(0)

    await send_event(ws, "turn.end", {"audio_errors": audio_errors})
