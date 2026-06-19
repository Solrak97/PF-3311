#!/usr/bin/env python3
"""Convenience launcher — run from src/backend: python scripts/export_study_data.py"""

from __future__ import annotations

import sys
from pathlib import Path

_ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "analysis"
if str(_ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(_ANALYSIS_DIR))

from export_study_data import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
