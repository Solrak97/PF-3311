from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

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
        self.refinement_dir = root / "refinement"
        self.sessions_dir = root / "sessions"
        for d in (
            self.raw_dir,
            self.behavioral_dir,
            self.validation_dir,
            self.refinement_dir,
            self.sessions_dir,
        ):
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

    def save_behavioral_yaml(self, profile: dict[str, Any]) -> dict[str, Any]:
        from app.profiles.yaml_profile import dump_profile_yaml, merge_constraints

        profile_id = _safe_id(str(profile.get("profile_id", "")))
        data = merge_constraints(profile)
        data["profile_id"] = profile_id
        path = self.behavioral_dir / f"{profile_id}.yaml"
        path.write_text(dump_profile_yaml(data), encoding="utf-8")
        from app.profiles.yaml_profile import profile_to_style_summary

        summary = {
            "profile_id": profile_id,
            "compiled_at": _utc_now_iso(),
            "style_summary": profile_to_style_summary(data),
            "yaml_profile": data,
        }
        self.save_behavioral(summary)
        return summary

    def load_behavioral_yaml(self, profile_id: str) -> dict[str, Any] | None:
        path = self.behavioral_dir / f"{_safe_id(profile_id)}.yaml"
        if not path.is_file():
            behavioral = self.load_behavioral(profile_id)
            if behavioral and isinstance(behavioral.get("yaml_profile"), dict):
                return behavioral["yaml_profile"]
            return None
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def load_final_profile(self, profile_id: str) -> dict[str, Any] | None:
        yaml_profile = self.load_behavioral_yaml(profile_id)
        if yaml_profile:
            return yaml_profile
        behavioral = self.load_behavioral(profile_id)
        if behavioral:
            return behavioral
        raw = self.load_raw(profile_id)
        if raw:
            from app.profiles.builder import compile_behavioral

            return compile_behavioral(raw)
        return None

    def list_profile_ids(self) -> list[str]:
        ids: set[str] = set()
        for folder in (self.behavioral_dir, self.raw_dir):
            for path in folder.glob("*.json"):
                ids.add(path.stem)
            for path in folder.glob("*.yaml"):
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

    def save_validation_aggregate(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        pid = _safe_id(profile_id)
        data = dict(payload)
        data["profile_id"] = pid
        if not data.get("created_at"):
            data["created_at"] = _utc_now_iso()
        path = self.validation_dir / f"{pid}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load_validation_aggregate(self, profile_id: str) -> dict[str, Any] | None:
        path = self.validation_dir / f"{_safe_id(profile_id)}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_refinement(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        pid = _safe_id(profile_id)
        data = dict(payload)
        data["profile_id"] = pid
        if not data.get("updated_at"):
            data["updated_at"] = _utc_now_iso()
        path = self.refinement_dir / f"{pid}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load_refinement(self, profile_id: str) -> dict[str, Any] | None:
        path = self.refinement_dir / f"{_safe_id(profile_id)}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_session(self, profile_id: str, phase: str, state: dict[str, Any]) -> dict[str, Any]:
        pid = _safe_id(profile_id)
        path = self.sessions_dir / f"{pid}_{phase}.json"
        data = dict(state)
        data["profile_id"] = pid
        data["phase"] = phase
        data["updated_at"] = _utc_now_iso()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

    def load_session(self, profile_id: str, phase: str) -> dict[str, Any] | None:
        path = self.sessions_dir / f"{_safe_id(profile_id)}_{phase}.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def delete_session(self, profile_id: str, phase: str) -> None:
        path = self.sessions_dir / f"{_safe_id(profile_id)}_{phase}.json"
        if path.is_file():
            path.unlink()

    def _all_profile_ids(self) -> set[str]:
        ids: set[str] = set(self.list_profile_ids())
        for path in self.refinement_dir.glob("*.json"):
            ids.add(path.stem)
        for path in self.validation_dir.glob("*.json"):
            name = path.stem
            if name.count("_") >= 2:
                parts = name.split("_")
                ids.add(parts[1])
            else:
                ids.add(name)
        for path in self.sessions_dir.glob("*.json"):
            if "_" in path.stem:
                ids.add(path.stem.rsplit("_", 1)[0])
        return ids

    def _validation_files_for(self, profile_id: str) -> list[Path]:
        pid = _safe_id(profile_id)
        files: list[Path] = []
        aggregate = self.validation_dir / f"{pid}.json"
        if aggregate.is_file():
            files.append(aggregate)
        for path in self.validation_dir.glob(f"*_{pid}_*.json"):
            if path.is_file():
                files.append(path)
        return files

    def _session_files_for(self, profile_id: str) -> list[Path]:
        pid = _safe_id(profile_id)
        return [p for p in self.sessions_dir.glob(f"{pid}_*.json") if p.is_file()]

    def list_profiles_detail(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for profile_id in sorted(self._all_profile_ids()):
            raw = self.load_raw(profile_id)
            behavioral = self.load_behavioral(profile_id)
            refinement = self.load_refinement(profile_id)
            validation_agg = self.load_validation_aggregate(profile_id)
            yaml_path = self.behavioral_dir / f"{profile_id}.yaml"
            json_path = self.behavioral_dir / f"{profile_id}.json"
            raw_path = self.raw_dir / f"{profile_id}.json"
            refinement_path = self.refinement_dir / f"{profile_id}.json"
            validation_files = self._validation_files_for(profile_id)
            session_files = self._session_files_for(profile_id)
            samples = (raw or {}).get("samples") or []
            sample_count = len(samples) if isinstance(samples, list) else 0
            summary = validation_agg.get("summary") if validation_agg else {}
            rows.append(
                {
                    "profile_id": profile_id,
                    "modeled_user_alias": (raw or behavioral or {}).get("modeled_user_alias", ""),
                    "created_at": (raw or behavioral or {}).get("created_at")
                    or (raw or behavioral or {}).get("compiled_at", ""),
                    "sample_count": sample_count,
                    "has_raw": raw_path.is_file(),
                    "has_behavioral_yaml": yaml_path.is_file(),
                    "has_behavioral_json": json_path.is_file(),
                    "has_refinement": refinement_path.is_file(),
                    "validation_count": len(validation_files),
                    "validation_passed": bool((summary or {}).get("passed")) if summary else None,
                    "active_sessions": [p.stem.rsplit("_", 1)[-1] for p in session_files],
                    "refinement_feedback_count": len((refinement or {}).get("feedback") or []),
                }
            )
        return rows

    def get_profile_detail(self, profile_id: str) -> dict[str, Any] | None:
        pid = _safe_id(profile_id)
        if pid not in self._all_profile_ids():
            return None
        raw = self.load_raw(pid)
        behavioral = self.load_behavioral(pid)
        yaml_profile = self.load_behavioral_yaml(pid)
        refinement = self.load_refinement(pid)
        validation_agg = self.load_validation_aggregate(pid)
        return {
            "profile_id": pid,
            "raw": raw,
            "behavioral": behavioral,
            "yaml_profile": yaml_profile,
            "refinement": refinement,
            "validation": validation_agg,
            "files": {
                "raw": (self.raw_dir / f"{pid}.json").is_file(),
                "behavioral_yaml": (self.behavioral_dir / f"{pid}.yaml").is_file(),
                "behavioral_json": (self.behavioral_dir / f"{pid}.json").is_file(),
                "refinement": (self.refinement_dir / f"{pid}.json").is_file(),
                "validation_records": len(self._validation_files_for(pid)),
                "sessions": [p.name for p in self._session_files_for(pid)],
            },
        }

    def delete_profile(self, profile_id: str) -> dict[str, int]:
        pid = _safe_id(profile_id)
        deleted = {
            "raw": 0,
            "behavioral_json": 0,
            "behavioral_yaml": 0,
            "refinement": 0,
            "validation": 0,
            "sessions": 0,
        }
        targets = [
            (self.raw_dir / f"{pid}.json", "raw"),
            (self.behavioral_dir / f"{pid}.json", "behavioral_json"),
            (self.behavioral_dir / f"{pid}.yaml", "behavioral_yaml"),
            (self.refinement_dir / f"{pid}.json", "refinement"),
        ]
        for path, key in targets:
            if path.is_file():
                path.unlink()
                deleted[key] = 1
        for path in self._validation_files_for(pid):
            path.unlink()
            deleted["validation"] += 1
        for path in self._session_files_for(pid):
            path.unlink()
            deleted["sessions"] += 1
        if sum(deleted.values()) == 0:
            raise ValueError("profile_not_found")
        return deleted

    def delete_all_profiles(self) -> dict[str, int]:
        totals = {
            "profiles_deleted": 0,
            "raw": 0,
            "behavioral_json": 0,
            "behavioral_yaml": 0,
            "refinement": 0,
            "validation": 0,
            "sessions": 0,
        }
        for profile_id in list(self._all_profile_ids()):
            try:
                result = self.delete_profile(profile_id)
                totals["profiles_deleted"] += 1
                for key in ("raw", "behavioral_json", "behavioral_yaml", "refinement", "validation", "sessions"):
                    totals[key] += result.get(key, 0)
            except ValueError:
                continue
        return totals

    def profile_stats(self) -> dict[str, int]:
        rows = self.list_profiles_detail()
        return {
            "profiles": len(rows),
            "with_yaml": sum(1 for r in rows if r.get("has_behavioral_yaml")),
            "with_validation": sum(1 for r in rows if r.get("validation_count", 0) > 0),
            "validation_passed": sum(1 for r in rows if r.get("validation_passed") is True),
        }
