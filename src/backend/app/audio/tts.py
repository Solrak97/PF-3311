import edge_tts

from app.audio.mp3_to_wav import mp3_to_wav
from app.audio.tts_split import split_for_tts
from app.config import settings


class EdgeTtsEngine:
    def __init__(self, voice: str | None = None) -> None:
        self._voice = voice or settings.edge_tts_voice

    async def synthesize_mp3(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(text, self._voice)
        out = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and chunk.get("data"):
                out.extend(chunk["data"])
        return bytes(out)

    async def synthesize_mp3_segments(self, text: str) -> list[bytes]:
        capped = text.strip()[: settings.max_tts_chars]
        if len(text.strip()) > settings.max_tts_chars:
            capped = capped.rstrip() + "…"
        parts = split_for_tts(capped, settings.tts_chunk_chars)
        return [await self.synthesize_mp3(part) for part in parts if part.strip()]

    async def synthesize_wav_segments(self, text: str) -> list[bytes]:
        """WAV (RIFF) segments for Godot — MP3 from Edge is decoded server-side."""
        segments: list[bytes] = []
        for mp3 in await self.synthesize_mp3_segments(text):
            wav = mp3_to_wav(mp3)
            if wav:
                segments.append(wav)
            elif mp3:
                # Godot can still try MP3 if WAV conversion fails.
                segments.append(mp3)
        return segments
