import asyncio

from app.audio.tts import EdgeTtsEngine


async def main() -> None:
    wavs = await EdgeTtsEngine().synthesize_wav_segments("Hola")
    print("segments", len(wavs))
    if wavs:
        print("magic", wavs[0][:4], "bytes", len(wavs[0]))


asyncio.run(main())
