#!/usr/bin/env python3
"""Export Suena Familiar study data from SQLite, validation files, and optional Godot logs."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from mappings import COMPOSITE_GROUPS, VALIDATION_RATING_KEYS, VALIDATION_SIMILARITY_KEYS

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "src" / "backend"
DEFAULT_EXPORTS = Path(__file__).resolve().parent / "exports"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")


def _default_db_path() -> Path:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    try:
        from app.config import settings

        db = Path(settings.sqlite_path)
        if db.is_absolute():
            return db
        return (BACKEND_ROOT / db).resolve()
    except Exception:
        return (BACKEND_ROOT / "data" / "experiment.db").resolve()


def _default_profiles_dir() -> Path:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    try:
        from app.config import settings

        p = Path(settings.profiles_data_dir)
        return p if p.is_absolute() else (BACKEND_ROOT / p).resolve()
    except Exception:
        return (BACKEND_ROOT / "data" / "profiles").resolve()


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    keys = fieldnames or sorted({k for row in rows for k in row})
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in keys})
    return len(rows)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def _mean_scores(responses: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    values: list[float] = []
    for key in keys:
        if key not in responses:
            continue
        try:
            values.append(float(responses[key]))
        except (TypeError, ValueError):
            continue
    return round(mean(values), 4) if values else None


def _fetch_sessions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            s.session_id,
            s.participant_id,
            s.condition,
            s.order_group,
            s.started_at,
            s.ended_at,
            s.duration_sec,
            s.message_count,
            s.end_reason,
            (
                SELECT COUNT(*) FROM turns t WHERE t.session_id = s.session_id
            ) AS logged_turns
        FROM sessions s
        ORDER BY COALESCE(s.ended_at, s.started_at) DESC, s.session_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_turns(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            id, participant_id, session_id, condition, order_group, turn_index,
            user_text, assistant_text, profile_used, retrieval_used, model_name,
            audio_error_count, created_at, profile_id, interaction_index, scenario_id,
            turn_metadata
        FROM turns
        ORDER BY session_id, turn_index, id
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw_meta = item.pop("turn_metadata", "{}") or "{}"
        try:
            item["turn_metadata_json"] = raw_meta
            item["turn_metadata"] = json.loads(raw_meta)
        except json.JSONDecodeError:
            item["turn_metadata_json"] = raw_meta
            item["turn_metadata"] = {}
        out.append(item)
    return out


def _fetch_questionnaires(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            id, run_session_id, session_id, participant_id, condition, order_group,
            interaction_index, questionnaire_after_interaction, profile_id,
            scenario_id, responses_json, created_at
        FROM questionnaire_responses
        ORDER BY created_at, id
        """
    ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["responses"] = json.loads(item.pop("responses_json", "{}") or "{}")
        except json.JSONDecodeError:
            item["responses"] = {}
        out.append(item)
    return out


def _flatten_questionnaire_wide(q: dict[str, Any]) -> dict[str, Any]:
    responses: dict[str, Any] = q.get("responses") or {}
    row: dict[str, Any] = {
        "questionnaire_id": q.get("id"),
        "run_session_id": q.get("run_session_id"),
        "session_id": q.get("session_id"),
        "participant_id": q.get("participant_id"),
        "condition": q.get("condition"),
        "order_group": q.get("order_group"),
        "interaction_index": q.get("interaction_index"),
        "questionnaire_after_interaction": q.get("questionnaire_after_interaction"),
        "profile_id": q.get("profile_id"),
        "scenario_id": q.get("scenario_id"),
        "created_at": q.get("created_at"),
    }
    for key, value in sorted(responses.items()):
        row[f"item__{key}"] = value
    for composite, keys in COMPOSITE_GROUPS.items():
        row[composite] = _mean_scores(responses, keys)
    return row


def _questionnaires_long(qs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for q in qs:
        responses: dict[str, Any] = q.get("responses") or {}
        for item_id, value in sorted(responses.items()):
            rows.append(
                {
                    "questionnaire_id": q.get("id"),
                    "run_session_id": q.get("run_session_id"),
                    "participant_id": q.get("participant_id"),
                    "condition": q.get("condition"),
                    "interaction_index": q.get("interaction_index"),
                    "item_id": item_id,
                    "value": value,
                }
            )
    return rows


def _infer_run_session_id(session_id: str) -> str:
    sid = session_id.strip()
    if "-i" in sid:
        return sid.rsplit("-i", 1)[0]
    return sid


def _build_runs_summary(
    turns: list[dict[str, Any]],
    questionnaires: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    turn_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "participant_id": "",
            "order_group": "",
            "turns_i1": 0,
            "turns_i2": 0,
            "has_i1": False,
            "has_i2": False,
            "condition_i1": "",
            "condition_i2": "",
        }
    )
    for turn in turns:
        sid = str(turn.get("session_id", ""))
        run_id = _infer_run_session_id(sid)
        bucket = turn_stats[run_id]
        bucket["participant_id"] = turn.get("participant_id", bucket["participant_id"])
        bucket["order_group"] = turn.get("order_group", bucket["order_group"])
        idx = int(turn.get("interaction_index") or 0)
        if idx == 1 or sid.endswith("-i1"):
            bucket["turns_i1"] += 1
            bucket["has_i1"] = True
            bucket["condition_i1"] = turn.get("condition", bucket["condition_i1"])
        elif idx == 2 or sid.endswith("-i2"):
            bucket["turns_i2"] += 1
            bucket["has_i2"] = True
            bucket["condition_i2"] = turn.get("condition", bucket["condition_i2"])

    q_stats: dict[str, dict[str, bool]] = defaultdict(lambda: {"q1": False, "q2": False})
    for q in questionnaires:
        run_id = str(q.get("run_session_id") or _infer_run_session_id(str(q.get("session_id", ""))))
        idx = int(q.get("interaction_index") or q.get("questionnaire_after_interaction") or 0)
        if idx == 1:
            q_stats[run_id]["q1"] = True
        elif idx == 2:
            q_stats[run_id]["q2"] = True
        turn_stats[run_id]["participant_id"] = q.get("participant_id", turn_stats[run_id]["participant_id"])
        turn_stats[run_id]["order_group"] = q.get("order_group", turn_stats[run_id]["order_group"])

    all_runs = sorted(set(turn_stats) | set(q_stats))
    rows: list[dict[str, Any]] = []
    for run_id in all_runs:
        t = turn_stats[run_id]
        q = q_stats[run_id]
        complete = t["has_i1"] and t["has_i2"] and q["q1"] and q["q2"]
        rows.append(
            {
                "run_session_id": run_id,
                "participant_id": t["participant_id"],
                "order_group": t["order_group"],
                "condition_i1": t["condition_i1"],
                "condition_i2": t["condition_i2"],
                "turns_i1": t["turns_i1"],
                "turns_i2": t["turns_i2"],
                "has_interaction_1": t["has_i1"],
                "has_interaction_2": t["has_i2"],
                "has_questionnaire_1": q["q1"],
                "has_questionnaire_2": q["q2"],
                "run_complete": complete,
            }
        )
    return rows


def _completeness_report(runs: list[dict[str, Any]], stats: dict[str, int]) -> str:
    lines = [
        "Suena Familiar — completeness report",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        f"Sessions (SQLite): {stats.get('sessions', 0)}",
        f"Turns: {stats.get('turns', 0)}",
        f"Questionnaires: {stats.get('questionnaires', 0)}",
        f"Experimental runs: {len(runs)}",
        f"Complete runs (2 interactions + 2 questionnaires): {sum(1 for r in runs if r.get('run_complete'))}",
        "",
    ]
    incomplete = [r for r in runs if not r.get("run_complete")]
    if incomplete:
        lines.append("Incomplete runs:")
        for r in incomplete:
            flags = []
            if not r.get("has_interaction_1"):
                flags.append("missing interaction 1")
            if not r.get("has_interaction_2"):
                flags.append("missing interaction 2")
            if not r.get("has_questionnaire_1"):
                flags.append("missing questionnaire 1")
            if not r.get("has_questionnaire_2"):
                flags.append("missing questionnaire 2")
            lines.append(
                f"  - {r.get('participant_id', '?')} / {r.get('run_session_id', '?')}: {', '.join(flags)}"
            )
    else:
        lines.append("All tracked runs are complete.")
    lines.append("")
    return "\n".join(lines)


def _export_validation(profiles_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validation_dir = profiles_dir / "validation"
    aggregates: list[dict[str, Any]] = []
    ratings_long: list[dict[str, Any]] = []
    if not validation_dir.is_dir():
        return aggregates, ratings_long

    for path in sorted(validation_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        name = path.stem
        is_aggregate = name.count("_") < 2
        profile_id = str(payload.get("profile_id") or (name if is_aggregate else name.split("_")[1]))
        summary = payload.get("summary") or {}
        aggregates.append(
            {
                "file": path.name,
                "profile_id": profile_id,
                "is_aggregate_file": is_aggregate,
                "validator_id": payload.get("validator_id", ""),
                "created_at": payload.get("created_at", ""),
                "passed": payload.get("passed", summary.get("passed")),
                "n_validators": summary.get("n_validators"),
                "mean_similarity": summary.get("mean_similarity"),
                "mean_naturalness": summary.get("mean_naturalness"),
                "mean_identity_safety": summary.get("mean_identity_safety"),
            }
        )
        for block in payload.get("ratings") or payload.get("validation_results") or []:
            scores = block.get("scores") or block
            base = {
                "file": path.name,
                "profile_id": profile_id,
                "validator_id": payload.get("validator_id") or block.get("validator_id", ""),
                "kind": block.get("kind", ""),
                "prompt": block.get("prompt", ""),
            }
            for key in VALIDATION_RATING_KEYS:
                if key in scores:
                    ratings_long.append({**base, "metric": key, "value": scores[key]})
        if not payload.get("ratings") and payload.get("validation_results"):
            for block in payload["validation_results"]:
                scores = block.get("scores") or block
                base = {
                    "file": path.name,
                    "profile_id": profile_id,
                    "validator_id": block.get("validator_id", payload.get("validator_id", "")),
                    "kind": "validation_result",
                    "prompt": block.get("prompt", ""),
                }
                for key in VALIDATION_RATING_KEYS:
                    if key in scores:
                        ratings_long.append({**base, "metric": key, "value": scores[key]})

    return aggregates, ratings_long


def _export_godot_logs(godot_logs_dir: Path) -> list[dict[str, Any]]:
    if not godot_logs_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(godot_logs_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for event in payload.get("events") or []:
            rows.append(
                {
                    "run_session_id": payload.get("session_id", path.stem),
                    "participant_id": payload.get("participant_id", ""),
                    "profile_a_id": payload.get("profile_a_id", ""),
                    "order": json.dumps(payload.get("order", []), ensure_ascii=False),
                    **{k: event.get(k) for k in event},
                }
            )
    return rows


def _turns_for_csv(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for turn in turns:
        row = dict(turn)
        row.pop("turn_metadata", None)
        rows.append(row)
    return rows


def _turns_jsonl(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "participant_id": t.get("participant_id"),
            "session_id": t.get("session_id"),
            "run_session_id": _infer_run_session_id(str(t.get("session_id", ""))),
            "interaction_index": t.get("interaction_index"),
            "condition": t.get("condition"),
            "order_group": t.get("order_group"),
            "turn_index": t.get("turn_index"),
            "user_text": t.get("user_text"),
            "assistant_text": t.get("assistant_text"),
            "profile_id": t.get("profile_id"),
            "scenario_id": t.get("scenario_id"),
            "profile_used": t.get("profile_used"),
            "retrieval_used": t.get("retrieval_used"),
            "model_name": t.get("model_name"),
            "created_at": t.get("created_at"),
            "turn_metadata": t.get("turn_metadata"),
        }
        for t in turns
    ]


def export_all(
    *,
    db_path: Path,
    out_dir: Path,
    profiles_dir: Path | None = None,
    godot_logs_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = _connect(db_path)

    sessions = _fetch_sessions(conn)
    turns = _fetch_turns(conn)
    questionnaires = _fetch_questionnaires(conn)
    conn.close()

    stats = {
        "sessions": len(sessions),
        "turns": len(turns),
        "questionnaires": len(questionnaires),
        "participants": len({s.get("participant_id") for s in sessions} | {q.get("participant_id") for q in questionnaires}),
    }

    questionnaires_wide = [_flatten_questionnaire_wide(q) for q in questionnaires]
    questionnaires_long = _questionnaires_long(questionnaires)
    runs_summary = _build_runs_summary(turns, questionnaires)

    # Paired within-subjects table for analysis (requires pandas)
    paired_rows: list[dict[str, Any]] = []
    try:
        import pandas as pd
        from db_extract import build_paired_scores

        paired_df = build_paired_scores(
            pd.DataFrame(questionnaires_wide),
            complete_runs_only=True,
            runs_summary=pd.DataFrame(runs_summary),
        )
        paired_rows = paired_df.to_dict("records")
    except ImportError:
        print("Warning: pandas not installed; paired_scores.csv skipped", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: could not build paired_scores.csv: {exc}", file=sys.stderr)

    counts = {
        "sessions.csv": _write_csv(out_dir / "sessions.csv", sessions),
        "turns.csv": _write_csv(out_dir / "turns.csv", _turns_for_csv(turns)),
        "turns.jsonl": _write_jsonl(out_dir / "turns.jsonl", _turns_jsonl(turns)),
        "questionnaires_wide.csv": _write_csv(out_dir / "questionnaires_wide.csv", questionnaires_wide),
        "questionnaires_long.csv": _write_csv(out_dir / "questionnaires_long.csv", questionnaires_long),
        "runs_summary.csv": _write_csv(out_dir / "runs_summary.csv", runs_summary),
        "paired_scores.csv": _write_csv(out_dir / "paired_scores.csv", paired_rows),
    }

    if profiles_dir:
        val_agg, val_long = _export_validation(profiles_dir)
        counts["validation_aggregates.csv"] = _write_csv(out_dir / "validation_aggregates.csv", val_agg)
        counts["validation_ratings_long.csv"] = _write_csv(out_dir / "validation_ratings_long.csv", val_long)

    if godot_logs_dir:
        godot_rows = _export_godot_logs(godot_logs_dir)
        counts["godot_run_events.jsonl"] = _write_jsonl(out_dir / "godot_run_events.jsonl", godot_rows)

    report = _completeness_report(runs_summary, stats)
    (out_dir / "completeness_report.txt").write_text(report, encoding="utf-8")

    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path.resolve()),
        "profiles_dir": str(profiles_dir.resolve()) if profiles_dir else None,
        "godot_logs_dir": str(godot_logs_dir.resolve()) if godot_logs_dir else None,
        "stats": stats,
        "files": counts,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export Suena Familiar study data for analysis.")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help=f"SQLite path (default: backend settings or { _default_db_path() })",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
        help="Profiles data directory for Fase 1 validation JSON export",
    )
    parser.add_argument(
        "--godot-logs",
        type=Path,
        default=None,
        help="Path to Godot user://experiment_logs/run/ (optional)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Output directory (default: {DEFAULT_EXPORTS}/<timestamp>)",
    )
    parser.add_argument(
        "--no-validation",
        action="store_true",
        help="Skip validation JSON export from profiles dir",
    )
    args = parser.parse_args(argv)

    db_path = (args.db or _default_db_path()).resolve()
    out_dir = (args.out or (DEFAULT_EXPORTS / _utc_stamp())).resolve()
    profiles_dir = None if args.no_validation else (args.profiles_dir or _default_profiles_dir()).resolve()
    godot_logs = args.godot_logs.resolve() if args.godot_logs else None

    try:
        manifest = export_all(
            db_path=db_path,
            out_dir=out_dir,
            profiles_dir=profiles_dir,
            godot_logs_dir=godot_logs,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Export written to: {out_dir}")
    print(json.dumps(manifest["stats"], indent=2))
    print((out_dir / "completeness_report.txt").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
