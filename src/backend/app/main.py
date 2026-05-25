import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.audio.tts import EdgeTtsEngine
from app.brain.ollama import OllamaBrain
from app.pipeline.turn import run_text_turn, send_event

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

_brain = OllamaBrain()
_tts = EdgeTtsEngine()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


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
                await send_event(
                    websocket,
                    "session.hello_ack",
                    {
                        "backend": "familiar",
                        "voice": settings.edge_tts_voice,
                        "model": settings.ollama_model,
                    },
                )
            elif typ == "turn.user_text":
                text = str(payload.get("text", ""))
                if not text.strip():
                    await send_event(websocket, "turn.end", {"error": "empty_text"})
                    continue
                await run_text_turn(websocket, text, _brain, _tts)
            else:
                logger.warning("unknown ws message type: %s", typ)
    except WebSocketDisconnect:
        logger.info("websocket disconnected")
