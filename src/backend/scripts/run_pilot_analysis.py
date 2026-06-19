#!/usr/bin/env python3
"""Launcher: cd src/backend && python scripts/run_pilot_analysis.py"""

from __future__ import annotations

import sys
from pathlib import Path

_ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(_ANALYSIS))

from run_pilot_analysis import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
