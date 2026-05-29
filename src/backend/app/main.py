import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.audio.tts import EdgeTtsEngine
from app.brain.factory import create_brain
from app.pipeline.turn import run_text_turn, send_event
from app.dashboard import build_dashboard_router
from app.storage.sqlite_store import SQLiteExperimentStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Familiar Buddy Backend")

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

app.include_router(build_dashboard_router(_store))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.resolved_llm_model,
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
                session_id = str(payload.get("session_id", "")).strip()
                participant_id = str(payload.get("participant_id", "")).strip()
                condition = str(payload.get("condition", "")).strip()
                logger.info(
                    "session.hello participant=%s session=%s condition=%s",
                    participant_id or "?",
                    session_id or "?",
                    condition or "?",
                )
                await send_event(
                    websocket,
                    "session.hello_ack",
                    {
                        "backend": "familiar",
                        "voice": settings.edge_tts_voice,
                        "model": settings.resolved_llm_model,
                        "llm_provider": settings.llm_provider,
                        "session_id": session_id,
                    },
                )
            elif typ == "turn.user_text":
                text = str(payload.get("text", ""))
                if not text.strip():
                    await send_event(websocket, "turn.end", {"error": "empty_text"})
                    continue
                participant_id = str(payload.get("participant_id", "unknown"))
                session_id = str(payload.get("session_id", "default"))
                condition = str(payload.get("condition", "B")).upper()
                if condition not in {"A", "B"}:
                    condition = "B"
                order_group = str(payload.get("order_group", "A-B"))
                try:
                    turn_index = int(payload.get("turn_index", 0))
                except (TypeError, ValueError):
                    turn_index = 0

                await run_text_turn(
                    websocket,
                    text,
                    _brain,
                    _tts,
                    store=_store,
                    participant_id=participant_id,
                    session_id=session_id,
                    condition=condition,
                    order_group=order_group,
                    turn_index=turn_index,
                    model_name=settings.resolved_llm_model,
                )
            else:
                logger.warning("unknown ws message type: %s", typ)
    except WebSocketDisconnect:
        logger.info("websocket disconnected")
