#!/usr/bin/env python3
"""Extract study data from SQLite and run within-subjects pilot analysis."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = Path(__file__).resolve().parent
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

from db_extract import default_db_path, default_profiles_dir, load_all  # noqa: E402
from export_study_data import export_all, _utc_stamp  # noqa: E402
from stats_pilot import run_full_analysis  # noqa: E402

DEFAULT_EXPORTS = ANALYSIS_DIR / "exports"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export + within-subjects statistical analysis for Suena Familiar pilot.",
    )
    parser.add_argument("--db", type=Path, default=None, help="SQLite database path")
    parser.add_argument("--profiles-dir", type=Path, default=None, help="Profiles data dir")
    parser.add_argument("--godot-logs", type=Path, default=None, help="Optional Godot run logs")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Export root directory (analysis/ subfolder created inside)",
    )
    parser.add_argument("--no-export", action="store_true", help="Skip CSV export; analyze DB only")
    parser.add_argument("--no-validation", action="store_true", help="Skip Fase 1 validation files")
    parser.add_argument(
        "--from-export",
        type=Path,
        default=None,
        help="Re-analyze an existing export directory instead of reading SQLite",
    )
    args = parser.parse_args(argv)

    if args.from_export:
        export_dir = args.from_export.resolve()
        from db_extract import load_from_export_dir

        frames = load_from_export_dir(export_dir)
        if "questionnaires" not in frames:
            print("Error: export dir missing questionnaires_wide.csv", file=sys.stderr)
            return 1
        frames["questionnaires"] = frames["questionnaires"]
        if "runs_summary" not in frames:
            frames["runs_summary"] = __import__("pandas").DataFrame()
        if "turns" not in frames:
            frames["turns"] = __import__("pandas").DataFrame()
        if "sessions" not in frames:
            frames["sessions"] = __import__("pandas").DataFrame()
        if "validation_aggregates" not in frames:
            frames["validation_aggregates"] = __import__("pandas").DataFrame()
        analysis_dir = export_dir / "analysis"
    else:
        db_path = (args.db or default_db_path()).resolve()
        profiles_dir = None if args.no_validation else (args.profiles_dir or default_profiles_dir()).resolve()
        export_dir = (args.out or (DEFAULT_EXPORTS / _utc_stamp())).resolve()

        if not args.no_export:
            try:
                manifest = export_all(
                    db_path=db_path,
                    out_dir=export_dir,
                    profiles_dir=profiles_dir,
                    godot_logs_dir=args.godot_logs.resolve() if args.godot_logs else None,
                )
                print(f"Export: {export_dir}")
                print(json.dumps(manifest["stats"], indent=2))
            except FileNotFoundError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1

        frames = load_all(db_path, profiles_dir, include_validation=not args.no_validation)
        analysis_dir = export_dir / "analysis"

    result = run_full_analysis(frames, analysis_dir)
    print(f"\nAnalysis written to: {analysis_dir}")
    print(json.dumps(result["summary"], indent=2))
    print("\n--- report.md (preview) ---\n")
    try:
        print(result["report"][:4000])
    except UnicodeEncodeError:
        print(result["report"][:4000].encode("ascii", errors="replace").decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
