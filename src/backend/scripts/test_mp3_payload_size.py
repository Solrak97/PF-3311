import asyncio
import base64

from app.audio.tts import EdgeTtsEngine


async def main() -> None:
    for text in ("Hola", "Esto es una prueba un poco más larga."):
        segs = await EdgeTtsEngine().synthesize_mp3_segments(text)
        for i, mp3 in enumerate(segs):
            b64_len = len(base64.b64encode(mp3))
            print(f"{text!r} seg[{i}] mp3={len(mp3)} b64={b64_len}")


asyncio.run(main())
