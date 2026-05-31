from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_SAFE_ID = re.compile(r"^[a-zA-Z0-9._-]+$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_id(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or not _SAFE_ID.match(cleaned):
        raise ValueError("invalid_id")
    return cleaned


class ProfileStore:
    def __init__(self, base_dir: str | None = None) -> None:
        root = Path(base_dir or settings.profiles_data_dir)
        self.raw_dir = root / "raw"
        self.behavioral_dir = root / "behavioral"
        self.validation_dir = root / "validation"
        for d in (self.raw_dir, self.behavioral_dir, self.validation_dir):
            d.mkdir(parents=True, exist_ok=True)

    def save_raw(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = _safe_id(str(payload.get("profile_id", "")))
        data = dict(payload)
        data["profile_id"] = profile_id
        if not data.get("created_at"):
            data["created_at"] = _utc_now_iso()
        path = self.raw_dir / f"{profile_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load_raw(self, profile_id: str) -> dict[str, Any] | None:
        path = self.raw_dir / f"{_safe_id(profile_id)}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_behavioral(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = _safe_id(str(payload.get("profile_id", "")))
        data = dict(payload)
        data["profile_id"] = profile_id
        path = self.behavioral_dir / f"{profile_id}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load_behavioral(self, profile_id: str) -> dict[str, Any] | None:
        path = self.behavioral_dir / f"{_safe_id(profile_id)}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_profile_ids(self) -> list[str]:
        ids: set[str] = set()
        for folder in (self.behavioral_dir, self.raw_dir):
            for path in folder.glob("*.json"):
                ids.add(path.stem)
        return sorted(ids)

    def save_validation(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = _safe_id(str(payload.get("profile_id", "unknown")))
        validator_id = _safe_id(str(payload.get("validator_id", "validator")))
        data = dict(payload)
        if not data.get("created_at"):
            data["created_at"] = _utc_now_iso()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = self.validation_dir / f"{validator_id}_{profile_id}_{stamp}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data
