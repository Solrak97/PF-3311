from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import settings

CONTROL_PROFILE_ID = "generic_control_agent"


def _default_control_path() -> Path:
    configured = Path(settings.control_profile_file)
    if configured.is_file():
        return configured
    repo_relative = Path(settings.profiles_dir) / "generic_control_agent.yaml"
    if repo_relative.is_file():
        return repo_relative
    return configured


@lru_cache(maxsize=1)
def load_control_profile(path: str | None = None) -> dict[str, Any]:
    profile_path = Path(path) if path else _default_control_path()
    if not profile_path.is_file():
        raise FileNotFoundError(f"control profile not found: {profile_path}")
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid control profile YAML: {profile_path}")
    data.setdefault("profile_id", CONTROL_PROFILE_ID)
    return data


def build_control_system_prompt(profile: dict[str, Any] | None = None) -> str:
    data = profile or load_control_profile()
    blocks = data.get("prompt_blocks") or {}
    role = str(blocks.get("role", "")).strip()
    behavioral = str(blocks.get("behavioral", "")).strip()
    guidance = data.get("conversation_guidance") or []
    parts: list[str] = []
    if role:
        parts.append(role)
    if behavioral:
        parts.append(behavioral)
    if isinstance(guidance, list) and guidance:
        parts.append("Guidelines:")
        for item in guidance:
            text = str(item).strip()
            if text:
                parts.append(f"- {text}")
    prohibited = (data.get("constraints") or {}).get("prohibited") or []
    if isinstance(prohibited, list) and prohibited:
        parts.append("Avoid:")
        for item in prohibited:
            text = str(item).strip()
            if text:
                parts.append(f"- {text}")
    return "\n\n".join(parts).strip()


def clear_control_profile_cache() -> None:
    load_control_profile.cache_clear()
