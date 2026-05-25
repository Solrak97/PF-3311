from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    edge_tts_voice: str = "en-US-AriaNeural"
    max_tts_chars: int = 2_000
    tts_chunk_chars: int = 240

    whisper_model_size: str = "base"
    whisper_device: str = "cpu"

    endpoint_silence_ms: int = 600
    max_utterance_ms: int = 30_000
    vad_backend: str = "energy"  # none | energy | silero (silero not implemented yet)

    cors_origins: list[str] = ["http://127.0.0.1:8000", "http://localhost:8000"]


settings = Settings()
