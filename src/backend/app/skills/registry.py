from __future__ import annotations

from pathlib import Path
from typing import Any

import json
import yaml

from app.config import settings


class SkillRegistry:
    def __init__(self, skills_dir: str | None = None) -> None:
        self.skills_dir = Path(skills_dir or settings.skills_dir)
        self._skills: dict[str, dict[str, Any]] = {}
        self._load_skills()

    def _load_skills(self) -> None:
        if not self.skills_dir.is_dir():
            return
        for path in sorted(self.skills_dir.iterdir()):
            if not path.is_file():
                continue
            data: dict[str, Any] | None = None
            try:
                if path.suffix.lower() == ".json":
                    parsed = json.loads(path.read_text(encoding="utf-8"))
                    data = parsed if isinstance(parsed, dict) else None
                elif path.suffix.lower() in {".yaml", ".yml"}:
                    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
                    data = parsed if isinstance(parsed, dict) else None
            except Exception:  # noqa: BLE001
                continue
            if not data:
                continue
            skill_id = str(data.get("skill_id") or data.get("id") or "").strip()
            if skill_id:
                self._skills[skill_id] = data

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        return self._skills.get(skill_id, {})

    @staticmethod
    def _sample_dicts(profile: dict[str, Any]) -> list[dict[str, Any]]:
        raw = profile.get("samples") or []
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [item for item in raw.values() if isinstance(item, dict)]
        return []

    def retrieve_context(
        self,
        profile: dict[str, Any],
        user_message: str,
        *,
        max_snippets: int | None = None,
    ) -> list[dict[str, Any]]:
        skill = self._skills.get("retrieve_context", {})
        limit = max_snippets or int(skill.get("max_snippets", 3))
        samples = self._sample_dicts(profile)
        if not samples:
            return []
        query = user_message.lower().strip()
        if not query:
            return samples[:limit]
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in samples:
            text = f"{item.get('prompt', '')} {item.get('response', '')}".lower()
            score = sum(1 for word in query.split() if len(word) > 3 and word in text)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored[0][0] > 0:
            return [item for _, item in scored[:limit]]
        return samples[:limit]
