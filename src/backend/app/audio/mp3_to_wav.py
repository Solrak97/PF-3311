"""Decode Edge-TTS MP3 bytes to a standard RIFF WAV for Godot AudioStreamWAV."""

from __future__ import annotations

import array
import io
import logging
import wave

import miniaudio

logger = logging.getLogger(__name__)


def mp3_to_wav(mp3: bytes) -> bytes:
    if not mp3:
        return b""
    try:
        decoded = miniaudio.decode(mp3)
    except Exception:
        logger.exception("miniaudio decode failed (%s bytes)", len(mp3))
        return b""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(decoded.nchannels)
        wf.setsampwidth(2)
        wf.setframerate(decoded.sample_rate)
        samples = array.array("h", decoded.samples)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()
