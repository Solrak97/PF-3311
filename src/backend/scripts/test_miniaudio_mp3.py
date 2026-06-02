import asyncio
import io
import struct
import wave

import edge_tts
import miniaudio


async def main() -> None:
    mp3 = bytearray()
    async for ch in edge_tts.Communicate("Hola", "es-MX-DaliaNeural").stream():
        if ch["type"] == "audio":
            mp3.extend(ch["data"])
    raw = bytes(mp3)
    print("mp3", len(raw))
    decoded = miniaudio.decode(raw)
    print("decoded", decoded.sample_rate, decoded.nchannels, len(decoded.samples))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(decoded.nchannels)
        wf.setsampwidth(2)
        wf.setframerate(decoded.sample_rate)
        pcm = struct.pack(f"<{len(decoded.samples)}h", *decoded.samples)
        wf.writeframes(pcm)
    wav = buf.getvalue()
    print("wav", len(wav), wav[:4])


asyncio.run(main())
