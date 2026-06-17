from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


@dataclass(frozen=True)
class Skill:
    skill_id: str
    name: str
    description: str
    path: Path
    data: dict[str, Any] = field(repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    @property
    def templates(self) -> dict[str, str]:
        raw = self.data.get("templates") or {}
        return {str(k): str(v) for k, v in raw.items() if v}

    @property
    def prompts(self) -> list[dict[str, Any]]:
        raw = self.data.get("prompts") or []
        return [item for item in raw if isinstance(item, dict)]

    @property
    def cycles(self) -> list[dict[str, Any]]:
        raw = self.data.get("cycles") or []
        return [item for item in raw if isinstance(item, dict)]

    @property
    def calibration(self) -> dict[str, Any]:
        raw = self.data.get("calibration") or {}
        return raw if isinstance(raw, dict) else {}

    @property
    def memory(self) -> dict[str, Any]:
        raw = self.data.get("memory") or {}
        return raw if isinstance(raw, dict) else {}

    @property
    def safety_rules(self) -> list[str]:
        raw = self.data.get("safety_rules") or []
        return [str(item) for item in raw if str(item).strip()]


class SkillLoader:
    """Load project skills from skills/<id>/skill.yaml (Cursor-style layout)."""

    def __init__(self, skills_root: str | Path | None = None) -> None:
        self.skills_root = Path(skills_root or settings.skills_dir)
        self._skills: dict[str, Skill] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.skills_root.is_dir():
            return
        candidates: list[Path] = []
        for child in sorted(self.skills_root.iterdir()):
            if child.is_dir():
                skill_file = child / "skill.yaml"
                if skill_file.is_file():
                    candidates.append(skill_file)
            elif child.suffix.lower() in {".yaml", ".yml"}:
                candidates.append(child)
        for path in candidates:
            skill = self._load_file(path)
            if skill is not None:
                self._skills[skill.skill_id] = skill

    @staticmethod
    def _load_file(path: Path) -> Skill | None:
        try:
            parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(parsed, dict):
            return None
        skill_id = str(parsed.get("skill_id") or parsed.get("id") or "").strip()
        if not skill_id:
            return None
        return Skill(
            skill_id=skill_id,
            name=str(parsed.get("name") or skill_id),
            description=str(parsed.get("description") or "").strip(),
            path=path,
            data=parsed,
        )

    def get(self, skill_id: str) -> Skill:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"skill_not_found:{skill_id}")
        return skill

    def get_skill(self, skill_id: str) -> dict[str, Any]:
        return self.get(skill_id).data

    def list_skills(self) -> list[str]:
        return sorted(self._skills)

    def prompt_by_id(self, skill_id: str, prompt_id: str) -> dict[str, str]:
        for item in self.get(skill_id).prompts:
            if str(item.get("id", "")) == prompt_id:
                return {
                    "id": str(item.get("id", "")),
                    "category": str(item.get("category", "open")),
                    "text": str(item.get("text", "")),
                }
        return {"id": prompt_id, "category": "open", "text": prompt_id}

    def retrieve_context(
        self,
        skill_id: str,
        profile: dict[str, Any],
        user_message: str,
        *,
        max_snippets: int | None = None,
        situation: str | None = None,
    ) -> list[dict[str, Any]]:
        skill = self.get(skill_id)
        retrieval = skill.data.get("retrieval") or {}
        limit = max_snippets or int(retrieval.get("max_snippets", 3))
        match_on = str(retrieval.get("match_on", "keyword"))
        samples = _sample_dicts(profile)
        if not samples:
            return []
        if match_on == "category" and situation and situation != "open":
            filtered = [
                item
                for item in samples
                if str(item.get("category", "")).lower() == situation.lower()
            ]
            if filtered:
                samples = filtered
        query = user_message.lower().strip()
        if not query:
            return samples[:limit]
        scored: list[tuple[int, dict[str, Any]]] = []
        for item in samples:
            text = f"{item.get('prompt', '')} {item.get('response', '')}".lower()
            score = sum(1 for word in query.split() if len(word) > 3 and word in text)
            scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] > 0:
            return [item for _, item in scored[:limit]]
        return samples[:limit]


def _sample_dicts(profile: dict[str, Any]) -> list[dict[str, Any]]:
    raw = profile.get("samples") or []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [item for item in raw.values() if isinstance(item, dict)]
    return []
