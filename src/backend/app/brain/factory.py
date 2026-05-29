from app.brain.base import Brain
from app.brain.ollama import OllamaBrain
from app.brain.openai_compat import OpenAICompatBrain
from app.config import settings


def create_brain() -> Brain:
    provider = settings.llm_provider.strip().lower()
    if provider == "openai_compat":
        return OpenAICompatBrain(
            base_url=settings.llm_base_url,
            model=settings.resolved_llm_model,
            api_key=settings.llm_api_key,
        )
    if provider != "ollama":
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider!r} (use ollama or openai_compat)")
    return OllamaBrain(
        base_url=settings.llm_base_url,
        model=settings.resolved_llm_model,
    )
