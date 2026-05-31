import asyncio
import json
import logging
import re
from typing import Any

from fastapi import WebSocket

from app.audio.tts import EdgeTtsEngine
from app.brain.ollama import OllamaBrain
from app.config import settings
from app.pipeline.text_clean import (
    contains_roleplay_markers,
    extract_roleplay_animation_hints,
    merge_animations,
    strip_roleplay_for_stream,
    strip_roleplay_markers,
)
from app.agents.chat_graph import prepare_chat_messages
from app.experiment.chat import resolved_profile_id
from app.profiles.store import ProfileStore
from app.storage.sqlite_store import SQLiteExperimentStore

logger = logging.getLogger(__name__)

JSON_BLOCK = re.compile(r"<JSON>\s*(\{.*?\})\s*</JSON>\s*$", re.DOTALL)
JSON_TAG = "<JSON>"
META_START = re.compile(r"\n\s*(?:<JSON|\{\s*\"animations\")")

SYSTEM_PROMPT = """You are Buddy, a friendly embodied assistant the user talks to in a 3D scene.
Keep answers concise and conversational (this will be spoken aloud). Prefer short paragraphs.
Use only the conversation history provided in this chat. Do not claim to remember other sessions or past visits.

Never use roleplay formatting in the spoken reply: no *asterisk actions*, no [bracket directions].
Write only words Buddy would say out loud.

You MUST still end every reply with the JSON animations line (required, on its own line):
<JSON>{"animations":[{"clip_id":"idle","blend_time":0.2}]}</JSON>

clip_id must be one of: idle, nod, wave, think. Pick one or two clips that match the mood (e.g. wave when greeting, nod when agreeing, think when pondering)."""


def _spoken_and_animations(full: str) -> tuple[str, list[dict[str, Any]]]:
    raw_visible = _visible_cutoff(full.strip())
    roleplay_anims = extract_roleplay_animation_hints(raw_visible)
    text = strip_roleplay_markers(raw_visible)
    m = JSON_BLOCK.search(full.strip())
    if not m:
        meta = META_START.search(full.strip())
        if meta:
            tail = full.strip()[meta.start() :]
            try:
                data = json.loads(tail.removeprefix("<JSON>").removesuffix("</JSON>").strip())
                anims = data.get("animations") if isinstance(data, dict) else []
                if isinstance(anims, list):
                    json_anims = [a for a in anims if isinstance(a, dict)]
                    return text, merge_animations(json_anims, roleplay_anims)
            except json.JSONDecodeError:
                pass
        return text, roleplay_anims
    raw = m.group(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        body = strip_roleplay_markers(full.strip()[: m.start()])
        return body, roleplay_anims
    anims = data.get("animations")
    if not isinstance(anims, list):
        anims = []
    json_anims = [a for a in anims if isinstance(a, dict)]
    return text, merge_animations(json_anims, roleplay_anims)


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
    visible = strip_roleplay_for_stream(_visible_cutoff(full))
    new_text = visible[sent_visible_len:]
    return new_text, len(visible)


async def send_event(ws: WebSocket, typ: str, payload: dict[str, Any]) -> None:
    await ws.send_text(json.dumps({"v": 1, "type": typ, "payload": payload}, ensure_ascii=False))


async def run_text_turn(
    ws: WebSocket,
    user_text: str,
    brain: OllamaBrain,
    tts: EdgeTtsEngine,
    *,
    store: SQLiteExperimentStore | None = None,
    profile_store: ProfileStore | None = None,
    participant_id: str = "unknown",
    session_id: str = "default",
    condition: str = "B",
    order_group: str = "A-B",
    turn_index: int = 0,
    model_name: str = "ollama",
    profile_id: str = "",
    interaction_index: int = 0,
    experiment_mode: bool = False,
) -> None:
    await send_event(ws, "listening.state", {"state": "processing"})
    profile_used = False
    retrieval_used = False
    cond = condition.upper()
    use_experiment_prompt = profile_store is not None and (
        cond == "B" or profile_id.strip() or experiment_mode
    )
    if use_experiment_prompt:
        prior: list[dict[str, Any]] = []
        if store is not None:
            prior = store.recent_turns_for_session(session_id=session_id, limit=8)
            logger.info(
                "session=%s condition=%s prior_turns=%s (session-scoped only)",
                session_id,
                condition,
                len(prior),
            )
        messages, profile_used, retrieval_used = await prepare_chat_messages(
            profile_store,
            condition=condition,
            profile_id=profile_id,
            user_message=user_text.strip(),
            session_turns=prior,
            include_ws_animation_protocol=True,
        )
    else:
        system = SYSTEM_PROMPT
        messages = [{"role": "system", "content": system}]
        if store is not None:
            prior = store.recent_turns_for_session(session_id=session_id, limit=8)
            logger.info(
                "session=%s condition=%s prior_turns=%s (session-scoped only)",
                session_id,
                condition,
                len(prior),
            )
            for item in prior:
                prev_user = str(item.get("user_text", "")).strip()
                prev_assistant = str(item.get("assistant_text", "")).strip()
                if prev_user:
                    messages.append({"role": "user", "content": prev_user})
                if prev_assistant:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": strip_roleplay_markers(prev_assistant),
                        }
                    )
        messages.append({"role": "user", "content": user_text.strip()})
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
    raw_visible = _visible_cutoff(full.strip())
    logger.info(
        "turn display_chars=%s anims=%s roleplay_in_raw=%s json_block=%s",
        len(display),
        [str(a.get("clip_id")) for a in anims],
        contains_roleplay_markers(raw_visible),
        bool(JSON_BLOCK.search(full.strip())),
    )
    if contains_roleplay_markers(raw_visible):
        logger.warning(
            "model emitted roleplay markers (stripped from chat/TTS): %r",
            raw_visible[:240],
        )
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
    raw_tts_len = len(tts_text.strip())
    tts_truncated = raw_tts_len > settings.max_tts_chars
    tts_chunk_count = 0
    if tts_text:
        try:
            segments = await tts.synthesize_mp3_segments(tts_text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("tts failed")
            await send_event(ws, "turn.end", {"error": f"tts: {exc}"})
            return

        total = len(segments)
        tts_chunk_count = total
        if total == 0:
            audio_errors.append("no_tts_segments")
            logger.warning("tts generated no segments (len=%s)", raw_tts_len)
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

    await send_event(
        ws,
        "turn.end",
        {
            "audio_errors": audio_errors,
            "tts_truncated": tts_truncated,
            "tts_text_len": raw_tts_len,
            "tts_chunk_count": tts_chunk_count,
        },
    )

    if store is not None:
        try:
            store.insert_turn(
                SQLiteExperimentStore.make_record(
                    participant_id=participant_id,
                    session_id=session_id,
                    condition=condition,
                    order_group=order_group,
                    turn_index=turn_index,
                    user_text=user_text,
                    assistant_text=display,
                    profile_used=profile_used,
                    retrieval_used=retrieval_used,
                    model_name=model_name,
                    audio_error_count=len(audio_errors),
                    profile_id=resolved_profile_id(condition=condition, profile_id=profile_id),
                    interaction_index=interaction_index,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("failed to store turn in sqlite")
