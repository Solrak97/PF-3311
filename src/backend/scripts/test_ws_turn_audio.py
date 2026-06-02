"""WS turn with TTS/audio diagnostics (from src/backend: uv run python scripts/test_ws_turn_audio.py)."""
import asyncio
import json
import sys

import httpx
import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws/session"
    text = sys.argv[1] if len(sys.argv) > 1 else "Hola"
    profile_id = sys.argv[2] if len(sys.argv) > 2 else "pf-001"
    session_id = "s-audio-test"
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "session.hello",
                    "payload": {
                        "client": "test",
                        "participant_id": "p-audio",
                        "session_id": session_id,
                        "condition": "A",
                        "order_group": "A-B",
                        "experiment_mode": True,
                        "profile_id": profile_id,
                    },
                }
            )
        )
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "turn.user_text",
                    "payload": {
                        "participant_id": "p-audio",
                        "session_id": session_id,
                        "condition": "A",
                        "order_group": "A-B",
                        "turn_index": 0,
                        "text": text,
                        "experiment_mode": True,
                        "profile_id": profile_id,
                        "interaction_index": 1,
                        "scenario_id": "daily_conversation",
                    },
                }
            )
        )
        tts_bytes = 0
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            if isinstance(raw, bytes):
                tts_bytes += len(raw)
                print(f"  tts binary: {len(raw)} bytes (total {tts_bytes})")
                continue
            msg = json.loads(raw)
            typ = msg.get("type", "")
            payload = msg.get("payload", {})
            if typ == "tts.chunk_meta":
                print(
                    f"  tts_meta[{payload.get('index', 0) + 1}/{payload.get('total', 1)}]: "
                    f"{payload.get('bytes', 0)} bytes"
                )
            elif typ == "tts.error":
                print(f"  tts.error: {payload}")
            elif typ == "turn.end":
                urls = payload.get("tts_audio_urls") or []
                print(f"  turn.end: chunks={payload.get('tts_chunk_count')} urls={len(urls)}")
                if payload.get("error"):
                    sys.exit(1)
                async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
                    for path in urls:
                        r = await client.get(path)
                        print(f"  GET {path}: {r.status_code} bytes={len(r.content)}")
                        r.raise_for_status()
                break
            elif typ not in {"listening.state", "llm.delta", "anim.command", "session.hello_ack", "llm.done"}:
                print(f"  {typ}: {payload}")


if __name__ == "__main__":
    asyncio.run(main())
