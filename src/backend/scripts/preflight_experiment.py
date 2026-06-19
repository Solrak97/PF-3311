#!/usr/bin/env python3
"""Pre-flight checks before running Fase 2 experiment sessions."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

ANALYSIS_ROOT = BACKEND_ROOT.parent / "analysis"
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        import httpx
    except ImportError:
        errors.append("httpx not installed — run: pip install -e src/backend")
        httpx = None  # type: ignore

    try:
        from app.config import settings

        db_path = Path(settings.sqlite_path)
        if not db_path.is_absolute():
            db_path = BACKEND_ROOT / db_path
    except Exception as exc:
        errors.append(f"Cannot load backend settings: {exc}")
        db_path = BACKEND_ROOT / "data" / "experiment.db"
        settings = None  # type: ignore

    if httpx is not None:
        base = settings.llm_base_url if settings else "http://127.0.0.1:11434"
        api = "http://127.0.0.1:8000"
        try:
            r = httpx.get(f"{api}/healthz", timeout=5.0)
            if r.status_code != 200:
                errors.append(f"Backend healthz returned {r.status_code}")
        except Exception as exc:
            errors.append(f"Backend not reachable at {api}: {exc}")

        try:
            r = httpx.get(f"{base}/api/tags", timeout=5.0)
            if r.status_code != 200:
                warnings.append(f"Ollama tags returned {r.status_code} at {base}")
        except Exception as exc:
            warnings.append(f"Ollama not reachable at {base}: {exc}")

        try:
            r = httpx.get(f"{api}/profiles", timeout=5.0)
            if r.status_code == 200:
                ids = r.json().get("profile_ids", [])
                if "generic_control_agent" not in ids:
                    warnings.append("Control profile generic_control_agent not in /profiles list")
            else:
                warnings.append(f"GET /profiles returned {r.status_code}")
        except Exception as exc:
            warnings.append(f"Could not list profiles: {exc}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.is_file():
        warnings.append(f"SQLite DB will be created on first session: {db_path}")
    else:
        conn = sqlite3.connect(db_path)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for table in ("turns", "sessions", "questionnaire_responses"):
            if table not in tables:
                warnings.append(f"Table missing in DB (will be created on use): {table}")

    try:
        import pandas  # noqa: F401
        import scipy  # noqa: F401
        import matplotlib  # noqa: F401
    except ImportError as exc:
        warnings.append(f"Analysis deps missing ({exc}) — pip install -r src/analysis/requirements.txt")

    report = {"errors": errors, "warnings": warnings, "db_path": str(db_path)}
    print(json.dumps(report, indent=2))
    if errors:
        print("\nFAILED preflight — fix errors before the study.", file=sys.stderr)
        return 1
    if warnings:
        print("\nPreflight passed with warnings.")
    else:
        print("\nPreflight OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
