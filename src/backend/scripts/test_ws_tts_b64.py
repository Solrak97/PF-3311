"""Verify TTS is sent as tts.audio_chunk (base64 JSON), not only binary."""
import asyncio
import base64
import json
import sys

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws/session"
    text = sys.argv[1] if len(sys.argv) > 1 else "Hola"
    session_id = "s-b64-test"
    async with websockets.connect(uri, max_size=8 * 1024 * 1024) as ws:
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "session.hello",
                    "payload": {
                        "client": "test",
                        "participant_id": "p-b64",
                        "session_id": session_id,
                        "condition": "A",
                        "order_group": "A-B",
                        "experiment_mode": True,
                        "profile_id": "pf-001",
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
                        "participant_id": "p-b64",
                        "session_id": session_id,
                        "condition": "A",
                        "order_group": "A-B",
                        "turn_index": 0,
                        "text": text,
                        "experiment_mode": True,
                        "profile_id": "pf-001",
                        "interaction_index": 1,
                        "scenario_id": "daily_conversation",
                    },
                }
            )
        )
        b64_chunks = 0
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            if isinstance(raw, bytes):
                print(f"  unexpected binary: {len(raw)} bytes")
                continue
            msg = json.loads(raw)
            typ = msg.get("type", "")
            payload = msg.get("payload", {})
            if typ == "tts.audio_chunk":
                b64_chunks += 1
                data = base64.b64decode(payload.get("data_b64", ""))
                print(
                    f"  tts.audio_chunk[{payload.get('index')}] "
                    f"fmt={payload.get('format')} bytes={len(data)} magic={data[:4]!r}"
                )
            elif typ == "turn.end":
                print(f"  turn.end tts_chunk_count={payload.get('tts_chunk_count')}")
                break
        if b64_chunks == 0:
            raise SystemExit("no tts.audio_chunk received")
        print("ok")


if __name__ == "__main__":
    asyncio.run(main())
