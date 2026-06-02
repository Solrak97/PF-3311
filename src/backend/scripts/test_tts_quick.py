import asyncio

from app.audio.tts import EdgeTtsEngine


async def main() -> None:
    tts = EdgeTtsEngine()
    try:
        segs = await tts.synthesize_mp3_segments("Hola, esto es una prueba de audio.")
        print("OK segments=", len(segs), "bytes=", [len(s) for s in segs])
    except Exception as exc:
        print("TTS_FAIL", type(exc).__name__, exc)


if __name__ == "__main__":
    asyncio.run(main())
