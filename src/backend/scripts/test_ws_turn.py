"""One-shot WebSocket turn test (run from src/backend: uv run python scripts/test_ws_turn.py)."""
import asyncio
import json
import sys

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws/session"
    user_text = sys.argv[1] if len(sys.argv) > 1 else "Say hello in one short sentence."
    print(f"Connecting to {uri} …")
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"v": 1, "type": "session.hello", "payload": {"client": "test"}}))
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "turn.user_text",
                    "payload": {
                        "participant_id": "p-demo",
                        "session_id": "s-demo",
                        "condition": "A",
                        "order_group": "A-B",
                        "turn_index": 1,
                        "text": user_text,
                    },
                }
            )
        )
        full = ""
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            if isinstance(raw, bytes):
                print(f"  tts binary: {len(raw)} bytes")
                continue
            msg = json.loads(raw)
            typ = msg.get("type", "")
            payload = msg.get("payload", {})
            if typ == "session.hello_ack":
                print(f"  hello_ack model={payload.get('model')}")
            elif typ == "llm.delta":
                chunk = payload.get("text", "")
                full += chunk
                print(chunk, end="", flush=True)
            elif typ == "llm.done":
                print(f"\n  llm.done ({len(payload.get('full_text', full))} chars)")
            elif typ == "anim.command":
                print(f"  anim: {payload.get('clip_id')} blend={payload.get('blend_time')}")
            elif typ == "tts.chunk_meta":
                idx = payload.get("index", 0)
                total = payload.get("total", 1)
                print(f"  tts_meta[{idx + 1}/{total}]: {payload.get('bytes')} bytes")
            elif typ == "tts.error":
                print(f"  tts.error: {payload.get('error')}")
            elif typ == "turn.end":
                err = payload.get("error")
                if err:
                    print(f"  turn.end ERROR: {err}")
                    sys.exit(1)
                audio_errors = payload.get("audio_errors", [])
                if audio_errors:
                    print(f"  turn.end OK (audio_errors={len(audio_errors)})")
                else:
                    print("  turn.end OK")
                break
            else:
                print(f"  {typ}: {payload}")


if __name__ == "__main__":
    asyncio.run(main())
