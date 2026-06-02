"""WebSocket conversation-open smoke test (from src/backend: uv run python scripts/test_ws_conversation_open.py)."""
import asyncio
import json
import sys

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8000/ws/session"
    profile_id = sys.argv[1] if len(sys.argv) > 1 else "pf-001"
    print(f"Connecting to {uri} profile={profile_id} …")
    async with websockets.connect(uri) as ws:
        await ws.send(
            json.dumps(
                {
                    "v": 1,
                    "type": "session.hello",
                    "payload": {
                        "client": "test",
                        "participant_id": "p-open",
                        "session_id": "s-open-test",
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
                    "type": "turn.conversation_open",
                    "payload": {
                        "participant_id": "p-open",
                        "session_id": "s-open-test",
                        "condition": "A",
                        "order_group": "A-B",
                        "turn_index": 0,
                        "experiment_mode": True,
                        "profile_id": profile_id,
                        "interaction_index": 1,
                        "scenario_id": "daily_conversation",
                    },
                }
            )
        )
        full = ""
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=120.0)
            if isinstance(raw, bytes):
                continue
            msg = json.loads(raw)
            typ = msg.get("type", "")
            payload = msg.get("payload", {})
            if typ == "session.hello_ack":
                print(f"  hello_ack model={payload.get('model')}")
            elif typ == "llm.delta":
                full += payload.get("text", "")
            elif typ == "llm.done":
                print(f"  reply: {payload.get('full_text', full)[:200]!r}")
            elif typ == "turn.end":
                err = payload.get("error")
                if err:
                    print(f"  turn.end ERROR: {err}")
                    sys.exit(1)
                print("  turn.end OK")
                break
            elif typ not in {"listening.state", "anim.command", "tts.chunk_meta"}:
                print(f"  {typ}: {payload}")


if __name__ == "__main__":
    asyncio.run(main())
