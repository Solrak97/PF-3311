"""Preview Spanish Edge TTS voices with Buddy-style Spanish sample text."""
import asyncio
from pathlib import Path

import edge_tts

SAMPLE = (
    "Hola, soy Buddy, encantada de acompañarte en el escenario. "
    "¿Quieres charlar un rato, o pasamos a la siguiente tarea?"
)

CANDIDATES = [
    "es-MX-DaliaNeural",
    "es-MX-JorgeNeural",
    "es-CO-SalomeNeural",
    "es-CL-CatalinaNeural",
    "es-CL-LorenzoNeural",
    "es-ES-ElviraNeural",
    "es-ES-AlvaroNeural",
    "es-US-PalomaNeural",
    "es-AR-ElenaNeural",
]


async def synth(voice: str, text: str) -> bytes:
    out = bytearray()
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk["type"] == "audio" and chunk.get("data"):
            out.extend(chunk["data"])
    return bytes(out)


async def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "data" / "voice_previews" / "es"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Sample: {SAMPLE!r}\n")
    for voice in CANDIDATES:
        path = out_dir / f"{voice}.mp3"
        print(f"  {voice} -> {path}")
        path.write_bytes(await synth(voice, SAMPLE))
    print(f"\nDone. {len(CANDIDATES)} files in {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
