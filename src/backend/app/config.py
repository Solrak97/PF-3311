from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM (provider-agnostic; use these for shipping / remote APIs)
    llm_provider: str = "ollama"  # ollama | openai_compat
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""

    # Legacy names (still read if LLM_* unset)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    sqlite_path: str = "./data/experiment.db"
    profiles_data_dir: str = "./data/profiles"
    profiles_dir: str = "./profiles"
    control_profile_file: str = "./profiles/generic_control_agent.yaml"
    skills_dir: str = "./skills"
    experiment_interaction_sec: int = 300

    edge_tts_voice: str = "en-US-AriaNeural"
    max_tts_chars: int = 2_000
    tts_chunk_chars: int = 240

    whisper_model_size: str = "base"
    whisper_device: str = "cpu"

    endpoint_silence_ms: int = 600
    max_utterance_ms: int = 30_000
    vad_backend: str = "energy"  # none | energy | silero

    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ]
    )

    @model_validator(mode="after")
    def _fill_llm_defaults(self) -> "Settings":
        if not self.llm_base_url.strip():
            object.__setattr__(self, "llm_base_url", self.ollama_base_url.rstrip("/"))
        if not self.llm_model.strip():
            object.__setattr__(self, "llm_model", self.ollama_model)
        object.__setattr__(self, "llm_base_url", self.llm_base_url.rstrip("/"))
        return self

    @property
    def resolved_llm_model(self) -> str:
        return self.llm_model.strip() or self.ollama_model


settings = Settings()
