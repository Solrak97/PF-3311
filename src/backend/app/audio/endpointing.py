from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Literal

from app.config import settings

VadBackend = Literal["none", "energy", "silero"]


@dataclass
class PttAudioBuffer:
    """Buffers PCM mono int16 little-endian while push-to-talk is held."""

    chunks: list[bytes] = field(default_factory=list)

    def clear(self) -> None:
        self.chunks.clear()

    def extend(self, pcm_s16le: bytes) -> None:
        if pcm_s16le:
            self.chunks.append(pcm_s16le)

    def take_bytes(self) -> bytes:
        data = b"".join(self.chunks)
        self.clear()
        return data


def pcm16le_rms_dbfs(chunk: bytes) -> float:
    """Rough RMS in dBFS for int16 mono LE PCM."""
    if len(chunk) < 2:
        return -120.0
    n = len(chunk) // 2
    if n == 0:
        return -120.0
    samples = struct.unpack(f"<{n}h", chunk[: n * 2])
    acc = sum(s * s for s in samples)
    rms = math.sqrt(acc / n) / 32768.0
    if rms <= 1e-12:
        return -120.0
    return 20.0 * math.log10(rms)


class EnergyEndpointingSegmenter:
    """
    Very small energy gate: treat frames above threshold as speech.
    Intended as a baseline before wiring Silero or similar.
    """

    def __init__(
        self,
        silence_ms: int | None = None,
        speech_dbfs: float = -35.0,
        frame_ms: int = 20,
        sample_rate: int = 16_000,
    ) -> None:
        self.silence_ms = silence_ms or settings.endpoint_silence_ms
        self.speech_dbfs = speech_dbfs
        self.frame_ms = frame_ms
        self.sample_rate = sample_rate
        self.bytes_per_frame = max(2, int(sample_rate * (frame_ms / 1000.0)) * 2)

    def should_endpoint(self, pcm_buffer: bytes, trailing_silence_ms: float) -> bool:
        if trailing_silence_ms >= self.silence_ms and len(pcm_buffer) > 0:
            return True
        return False


class SileroVadSegmenter:
    """Reserved for a future Silero VAD integration (torch / onnx runtime)."""

    def __init__(self) -> None:
        raise NotImplementedError(
            "Silero VAD is planned; set VAD_BACKEND=energy or none for now, "
            "or implement SileroVadSegmenter with your preferred runtime."
        )
