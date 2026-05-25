import io
import wave
from typing import Any

import numpy as np

from app.config import settings


class FasterWhisperSTT:
    """Lazy-loaded faster-whisper model for offline transcription."""

    def __init__(self, model_size: str | None = None, device: str | None = None) -> None:
        self._model_size = model_size or settings.whisper_model_size
        self._device = device or settings.whisper_device
        self._model: Any = None

    def _ensure(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(self._model_size, device=self._device)

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """16-bit PCM WAV bytes → text."""
        self._ensure()
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        if sample_width != 2:
            raise ValueError("Only 16-bit WAV is supported")
        audio_i16 = np.frombuffer(frames, dtype=np.int16)
        if channels == 2:
            audio_i16 = audio_i16.reshape(-1, 2).mean(axis=1).astype(np.int16)
        audio_f32 = audio_i16.astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(audio_f32, language=None)
        return "".join(segment.text for segment in segments).strip()
