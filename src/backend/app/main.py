import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.audio.delivery import pop_turn_audio
from app.audio.tts import EdgeTtsEngine
from app.brain.factory import create_brain
from app.pipeline.turn import run_text_turn, send_event
from app.dashboard import build_dashboard_router
from app.experiment.routes import build_experiment_router
from app.profiles.store import ProfileStore
from app.storage.sqlite_store import SQLiteExperimentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PF-3311 Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_brain = create_brain()
_tts = EdgeTtsEngine()
_store = SQLiteExperimentStore(settings.sqlite_path)
_profile_store = ProfileStore(settings.profiles_data_dir)


def _session_fields(payload: dict) -> tuple[str, str, str, str]:
    session_id = str(payload.get("session_id", "")).strip()
    participant_id = str(payload.get("participant_id", "")).strip() or "unknown"
    condition = str(payload.get("condition", "B")).upper()
    if condition not in {"A", "B"}:
        condition = "B"
    order_group = str(payload.get("order_group", "A-B"))
    return session_id, participant_id, condition, order_group


async def _ack_session(
    websocket: WebSocket,
    *,
    session_id: str,
    fresh: bool = False,
) -> None:
    payload: dict[str, Any] = {
        "backend": "familiar",
        "voice": settings.edge_tts_voice,
        "model": settings.resolved_llm_model,
        "llm_provider": settings.llm_provider,
        "session_id": session_id,
    }
    if fresh:
        payload["fresh"] = True
    await send_event(websocket, "session.hello_ack", payload)


app.include_router(build_dashboard_router(_store, _profile_store))
app.include_router(build_experiment_router(_profile_store, _brain, _store))


@app.get("/audio/turn/{token}")
async def get_turn_audio(token: str) -> Response:
    mp3 = pop_turn_audio(token)
    if not mp3:
        raise HTTPException(status_code=404, detail="audio not found or expired")
    logger.info("audio GET token=%s bytes=%s", token[:48], len(mp3))
    return Response(content=mp3, media_type="audio/mpeg")


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    from app.brain.embeddings import embed_model_available

    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.resolved_llm_model,
        "llm_base_url": settings.llm_base_url,
        "llm_fallback_base_url": settings.llm_fallback_base_url or None,
        "llm_fallback_model": settings.resolved_llm_fallback_model or None,
        "embed_model": settings.ollama_embed_model,
        "embeddings_available": embed_model_available(),
        "classifier_mode": settings.situation_classifier_mode,
        "planner_mode": settings.behavioral_planner_mode,
        "llm_timeout_sec": settings.llm_timeout_sec,
    }


@app.websocket("/ws/session")
async def ws_session(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg: Any = json.loads(raw)
            except json.JSONDecodeError:
                await send_event(websocket, "turn.end", {"error": "invalid_json"})
                continue
            if not isinstance(msg, dict):
                await send_event(websocket, "turn.end", {"error": "invalid_message"})
                continue
            typ = str(msg.get("type", ""))
            payload = msg.get("payload")
            if not isinstance(payload, dict):
                payload = {}

            if typ == "session.hello":
                session_id, participant_id, condition, order_group = _session_fields(payload)
                if not session_id:
                    await send_event(
                        websocket,
                        "session.hello_ack",
                        {"error": "missing_session_id"},
                    )
                    continue
                logger.info(
                    "session.hello participant=%s session=%s condition=%s order=%s",
                    participant_id,
                    session_id,
                    condition,
                    order_group,
                )
                _store.record_session_start(
                    session_id=session_id,
                    participant_id=participant_id,
                    condition=condition,
                    order_group=order_group,
                )
                await _ack_session(websocket, session_id=session_id)
            elif typ in ("session.new", "session.reset"):
                session_id, participant_id, condition, order_group = _session_fields(payload)
                if not session_id:
                    await send_event(
                        websocket,
                        "session.hello_ack",
                        {"error": "missing_session_id"},
                    )
                    continue
                logger.info(
                    "session.new participant=%s session=%s order=%s",
                    participant_id,
                    session_id,
                    order_group,
                )
                _store.record_session_start(
                    session_id=session_id,
                    participant_id=participant_id,
                    condition=condition,
                    order_group=order_group,
                )
                await _ack_session(websocket, session_id=session_id, fresh=True)
            elif typ == "session.end":
                session_id, participant_id, condition, order_group = _session_fields(payload)
                if not session_id:
                    await send_event(websocket, "session.end_ack", {"error": "missing_session_id"})
                    continue
                try:
                    duration_sec = int(payload.get("duration_sec", 0))
                except (TypeError, ValueError):
                    duration_sec = 0
                try:
                    message_count = int(payload.get("message_count", 0))
                except (TypeError, ValueError):
                    message_count = 0
                end_reason = str(payload.get("reason", "")).strip()
                logger.info(
                    "session.end participant=%s session=%s duration=%ss messages=%s reason=%s",
                    participant_id,
                    session_id,
                    duration_sec,
                    message_count,
                    end_reason or "?",
                )
                _store.record_session_end(
                    session_id=session_id,
                    duration_sec=duration_sec if duration_sec > 0 else None,
                    message_count=message_count if message_count > 0 else None,
                    end_reason=end_reason,
                    participant_id=participant_id,
                    condition=condition,
                    order_group=order_group,
                )
                await send_event(
                    websocket,
                    "session.end_ack",
                    {"session_id": session_id},
                )
            elif typ in ("turn.user_text", "turn.conversation_open"):
                conversation_open = typ == "turn.conversation_open"
                logger.info("ws in %s session=%s", typ, str(payload.get("session_id", "")))
                text = str(payload.get("text", ""))
                if not conversation_open and not text.strip():
                    await send_event(websocket, "turn.end", {"error": "empty_text"})
                    continue
                participant_id = str(payload.get("participant_id", "unknown"))
                session_id = str(payload.get("session_id", "")).strip()
                if not session_id:
                    await send_event(
                        websocket,
                        "turn.end",
                        {"error": "missing_session_id"},
                    )
                    continue
                condition = str(payload.get("condition", "B")).upper()
                if condition not in {"A", "B"}:
                    condition = "B"
                order_group = str(payload.get("order_group", "A-B"))
                try:
                    turn_index = int(payload.get("turn_index", 0))
                except (TypeError, ValueError):
                    turn_index = 0
                profile_id = str(payload.get("profile_id", "")).strip()
                try:
                    interaction_index = int(payload.get("interaction_index", 0))
                except (TypeError, ValueError):
                    interaction_index = 0
                experiment_mode = bool(payload.get("experiment_mode", False))
                scenario_id = str(payload.get("scenario_id", "")).strip() or None

                await run_text_turn(
                    websocket,
                    text,
                    _brain,
                    _tts,
                    store=_store,
                    profile_store=_profile_store,
                    participant_id=participant_id,
                    session_id=session_id,
                    condition=condition,
                    order_group=order_group,
                    turn_index=turn_index,
                    model_name=settings.resolved_llm_model,
                    profile_id=profile_id,
                    interaction_index=interaction_index,
                    experiment_mode=experiment_mode,
                    scenario_id=scenario_id,
                    conversation_open=conversation_open,
                )
            else:
                logger.warning("unknown ws message type: %s", typ)
    except WebSocketDisconnect:
        logger.info("websocket disconnected")
