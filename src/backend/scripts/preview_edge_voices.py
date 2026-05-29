"""Generate short MP3 previews for comparing Edge TTS voices.

Usage:
  uv run python scripts/preview_edge_voices.py
  uv run python scripts/preview_edge_voices.py en-US-GuyNeural en-US-AnaNeural

Outputs to data/voice_previews/<voice>.mp3
"""
import asyncio
import sys
from pathlib import Path

import edge_tts

# Friendly lines that match the familiar buddy tone
SAMPLE = (
    "Hey! I'm your little wooden buddy. "
    "Want to chat for a bit, or should we try the next task?"
)

# Good en-US picks for a warm / playful companion (not news-anchor formal)
DEFAULT_CANDIDATES = [
    "en-US-AnaNeural",  # lighter, younger female
    "en-US-JennyNeural",  # friendly, conversational female
    "en-US-GuyNeural",  # casual male
    "en-US-EricNeural",  # warm male
    "en-US-ChristopherNeural",  # calm, approachable male
    "en-US-BrianNeural",  # upbeat male
    "en-US-AndrewNeural",  # clear, friendly male
    "en-US-AriaNeural",  # current default (more formal)
]


async def synth(voice: str, text: str) -> bytes:
    out = bytearray()
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio" and chunk.get("data"):
            out.extend(chunk["data"])
    return bytes(out)


async def main() -> None:
    voices = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_CANDIDATES
    out_dir = Path(__file__).resolve().parents[1] / "data" / "voice_previews"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Sample text: {SAMPLE!r}\n")
    for voice in voices:
        path = out_dir / f"{voice}.mp3"
        print(f"  {voice} -> {path}")
        path.write_bytes(await synth(voice, SAMPLE))
    print(f"\nDone. Open files in {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
