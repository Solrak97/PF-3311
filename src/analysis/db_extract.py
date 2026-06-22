"""Load experiment data from SQLite into pandas DataFrames."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from mappings import ALL_OUTCOME_COLS, COMPOSITE_GROUPS

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "src" / "backend"


def default_db_path() -> Path:
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    try:
        from app.config import settings

        db = Path(settings.sqlite_path)
        return db if db.is_absolute() else (BACKEND_ROOT / db).resolve()
    except Exception:
        return (BACKEND_ROOT / "data" / "experiment.db").resolve()


def default_profiles_dir() -> Path:
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


def _mean_scores(responses: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    values: list[float] = []
    for key in keys:
        if key not in responses:
            continue
        try:
            values.append(float(responses[key]))
        except (TypeError, ValueError):
            continue
    return round(sum(values) / len(values), 4) if values else None


def infer_run_session_id(session_id: str) -> str:
    sid = str(session_id).strip()
    if "-i" in sid:
        return sid.rsplit("-i", 1)[0]
    return sid


def load_sessions(db_path: Path) -> pd.DataFrame:
    conn = _connect(db_path)
    df = pd.read_sql_query(
        """
        SELECT
            s.*,
            (SELECT COUNT(*) FROM turns t WHERE t.session_id = s.session_id) AS logged_turns
        FROM sessions s
        ORDER BY COALESCE(s.ended_at, s.started_at)
        """,
        conn,
    )
    conn.close()
    if not df.empty:
        df["run_session_id"] = df["session_id"].map(infer_run_session_id)
    return df


def load_turns(db_path: Path) -> pd.DataFrame:
    conn = _connect(db_path)
    df = pd.read_sql_query("SELECT * FROM turns ORDER BY session_id, turn_index, id", conn)
    conn.close()
    if df.empty:
        return df
    df["run_session_id"] = df["session_id"].map(infer_run_session_id)

    def _parse_meta(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    df["turn_metadata"] = df["turn_metadata"].map(_parse_meta)
    for col in ("profile_used", "retrieval_used"):
        if col in df.columns:
            df[col] = df[col].astype(bool)
    return df


def load_questionnaires_raw(db_path: Path) -> pd.DataFrame:
    conn = _connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM questionnaire_responses ORDER BY created_at, id",
        conn,
    )
    conn.close()
    if df.empty:
        return df

    def _parse_resp(raw: Any) -> dict[str, Any]:
        try:
            return json.loads(raw or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    df["responses"] = df["responses_json"].map(_parse_resp)
    return df


def enrich_questionnaires(df: pd.DataFrame) -> pd.DataFrame:
    """Add composite PI columns and flat item columns."""
    if df.empty:
        return df
    out = df.copy()
    for composite, keys in COMPOSITE_GROUPS.items():
        out[composite] = out["responses"].map(lambda r: _mean_scores(r or {}, keys))
    for _, row in out.iterrows():
        responses = row.get("responses") or {}
        for key, value in responses.items():
            out.loc[row.name, f"item__{key}"] = value
    return out


def load_questionnaires(db_path: Path) -> pd.DataFrame:
    return enrich_questionnaires(load_questionnaires_raw(db_path))


def load_runs_summary(turns: pd.DataFrame, questionnaires: pd.DataFrame) -> pd.DataFrame:
    from export_study_data import _build_runs_summary

    turn_rows = turns.to_dict("records") if not turns.empty else []
    q_rows = questionnaires.to_dict("records") if not questionnaires.empty else []
    return pd.DataFrame(_build_runs_summary(turn_rows, q_rows))


def load_validation(profiles_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    from export_study_data import _export_validation

    agg, long = _export_validation(profiles_dir)
    return pd.DataFrame(agg), pd.DataFrame(long)


def load_all(
    db_path: Path | None = None,
    profiles_dir: Path | None = None,
    *,
    include_validation: bool = True,
) -> dict[str, pd.DataFrame]:
    db = (db_path or default_db_path()).resolve()
    profiles = (profiles_dir or default_profiles_dir()).resolve()

    sessions = load_sessions(db)
    turns = load_turns(db)
    questionnaires = load_questionnaires(db)
    runs_summary = load_runs_summary(turns, questionnaires)

    frames: dict[str, pd.DataFrame] = {
        "sessions": sessions,
        "turns": turns,
        "questionnaires": questionnaires,
        "runs_summary": runs_summary,
    }
    if include_validation:
        frames["validation_aggregates"], frames["validation_ratings"] = load_validation(profiles)
    return frames


def load_from_export_dir(export_dir: Path) -> dict[str, pd.DataFrame]:
    """Load CSV exports produced by export_study_data.py."""
    export_dir = export_dir.resolve()
    frames: dict[str, pd.DataFrame] = {}
    mapping = {
        "sessions": "sessions.csv",
        "turns": "turns.csv",
        "questionnaires": "questionnaires_wide.csv",
        "runs_summary": "runs_summary.csv",
        "validation_aggregates": "validation_aggregates.csv",
        "validation_ratings": "validation_ratings_long.csv",
        "paired_scores": "paired_scores.csv",
    }
    for key, fname in mapping.items():
        path = export_dir / fname
        if not path.is_file() or path.stat().st_size == 0:
            continue
        try:
            frames[key] = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            continue
    if "questionnaires" in frames and "responses" not in frames["questionnaires"].columns:
        frames["questionnaires_raw"] = frames["questionnaires"]
    return frames


def filter_complete_runs(
    questionnaires: pd.DataFrame,
    runs_summary: pd.DataFrame,
) -> pd.DataFrame:
    if questionnaires.empty or runs_summary.empty:
        return questionnaires.iloc[0:0]
    complete_ids = set(
        runs_summary.loc[
            runs_summary["run_complete"].astype(str).str.lower().isin({"true", "1", "yes"}),
            "run_session_id",
        ].astype(str)
    )
    if not complete_ids:
        return questionnaires.iloc[0:0]
    return questionnaires[questionnaires["run_session_id"].astype(str).isin(complete_ids)].copy()


def dedupe_questionnaires_per_condition(df: pd.DataFrame) -> pd.DataFrame:
    """Keep latest questionnaire per participant × condition."""
    if df.empty:
        return df
    sort_cols = ["participant_id", "condition", "created_at"]
    if "questionnaire_id" in df.columns:
        sort_cols.append("questionnaire_id")
    elif "id" in df.columns:
        sort_cols.append("id")
    out = df.sort_values(sort_cols)
    return out.groupby(["participant_id", "condition"], as_index=False).tail(1)


def build_paired_scores(
    questionnaires: pd.DataFrame,
    *,
    complete_runs_only: bool = True,
    runs_summary: pd.DataFrame | None = None,
    outcome_cols: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """
    Within-subjects wide table: one row per participant with _A / _B / _diff columns.
    """
    outcomes = outcome_cols or ALL_OUTCOME_COLS
    df = questionnaires.copy()
    if complete_runs_only and runs_summary is not None and not runs_summary.empty:
        df = filter_complete_runs(df, runs_summary)
    df = dedupe_questionnaires_per_condition(df)

    meta_cols = ["participant_id", "run_session_id", "order_group", "profile_id", "scenario_id"]
    rows: list[dict[str, Any]] = []

    for participant_id, grp in df.groupby("participant_id"):
        a_rows = grp[grp["condition"].astype(str).str.upper() == "A"]
        b_rows = grp[grp["condition"].astype(str).str.upper() == "B"]
        if a_rows.empty or b_rows.empty:
            continue
        a = a_rows.iloc[-1]
        b = b_rows.iloc[-1]
        row: dict[str, Any] = {
            "participant_id": participant_id,
            "run_session_id": a.get("run_session_id", b.get("run_session_id")),
            "order_group": a.get("order_group", b.get("order_group")),
            "profile_id_A": a.get("profile_id"),
            "scenario_id_A": a.get("scenario_id"),
            "scenario_id_B": b.get("scenario_id"),
            "interaction_index_A": a.get("interaction_index"),
            "interaction_index_B": b.get("interaction_index"),
        }
        for col in outcomes:
            if col not in grp.columns:
                continue
            va, vb = a.get(col), b.get(col)
            if pd.isna(va) or pd.isna(vb):
                continue
            row[f"{col}_A"] = float(va)
            row[f"{col}_B"] = float(vb)
            row[f"{col}_diff"] = float(va) - float(vb)
        rows.append(row)

    return pd.DataFrame(rows)


def build_turn_summaries(turns: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    if turns.empty:
        return pd.DataFrame()

    t = turns.copy()
    if not sessions.empty:
        t = t.merge(
            sessions[["session_id", "duration_sec", "message_count", "end_reason"]],
            on="session_id",
            how="left",
        )

    per_session = (
        t.groupby(["participant_id", "condition", "interaction_index", "session_id"], as_index=False)
        .agg(
            n_turns=("turn_index", "count"),
            retrieval_rate=("retrieval_used", "mean"),
            profile_used_rate=("profile_used", "mean"),
            avg_user_chars=("user_text", lambda s: s.astype(str).str.len().mean()),
            avg_assistant_chars=("assistant_text", lambda s: s.astype(str).str.len().mean()),
            audio_errors=("audio_error_count", "sum"),
            duration_sec=("duration_sec", "first"),
        )
    )

    paired_rows: list[dict[str, Any]] = []
    for participant_id, grp in per_session.groupby("participant_id"):
        a = grp[grp["condition"].astype(str).str.upper() == "A"]
        b = grp[grp["condition"].astype(str).str.upper() == "B"]
        if a.empty or b.empty:
            continue
        ar, br = a.iloc[-1], b.iloc[-1]
        paired_rows.append(
            {
                "participant_id": participant_id,
                "n_turns_A": int(ar["n_turns"]),
                "n_turns_B": int(br["n_turns"]),
                "n_turns_diff": int(ar["n_turns"] - br["n_turns"]),
                "retrieval_rate_A": float(ar["retrieval_rate"]),
                "retrieval_rate_B": float(br["retrieval_rate"]),
                "avg_user_chars_A": float(ar["avg_user_chars"]),
                "avg_user_chars_B": float(br["avg_user_chars"]),
                "duration_sec_A": ar.get("duration_sec"),
                "duration_sec_B": br.get("duration_sec"),
            }
        )
    return pd.DataFrame(paired_rows)


def build_item_level_paired(questionnaires: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
    df = dedupe_questionnaires_per_condition(questionnaires)
    if kwargs.get("complete_runs_only") and kwargs.get("runs_summary") is not None:
        df = filter_complete_runs(df, kwargs["runs_summary"])
    item_cols = [c for c in df.columns if c.startswith("item__")]
    rows: list[dict[str, Any]] = []
    for item_col in item_cols:
        item_id = item_col.replace("item__", "", 1)
        sub = df[["participant_id", "condition", item_col]].dropna()
        a = sub[sub["condition"].astype(str).str.upper() == "A"].set_index("participant_id")[item_col]
        b = sub[sub["condition"].astype(str).str.upper() == "B"].set_index("participant_id")[item_col]
        common = a.index.intersection(b.index)
        if len(common) == 0:
            continue
        diff = a.loc[common] - b.loc[common]
        rows.append(
            {
                "item_id": item_id,
                "n_pairs": len(common),
                "mean_A": a.loc[common].mean(),
                "mean_B": b.loc[common].mean(),
                "mean_diff": diff.mean(),
                "sd_diff": diff.std(ddof=1) if len(common) > 1 else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("item_id")


def build_order_effects(questionnaires: pd.DataFrame) -> pd.DataFrame:
    """Exploratory: first vs second interaction (regardless of condition)."""
    df = dedupe_questionnaires_per_condition(questionnaires)
    if df.empty or "interaction_index" not in df.columns:
        return pd.DataFrame()
    outcome_cols = [c for c in ALL_OUTCOME_COLS if c in df.columns]
    rows: list[dict[str, Any]] = []
    for outcome in outcome_cols:
        g = df.dropna(subset=[outcome])
        i1 = g[g["interaction_index"] == 1][outcome]
        i2 = g[g["interaction_index"] == 2][outcome]
        if len(i1) < 2 or len(i2) < 2:
            continue
        rows.append(
            {
                "outcome": outcome,
                "mean_interaction_1": i1.mean(),
                "mean_interaction_2": i2.mean(),
                "sd_interaction_1": i1.std(ddof=1),
                "sd_interaction_2": i2.std(ddof=1),
                "n_interaction_1": len(i1),
                "n_interaction_2": len(i2),
            }
        )
    return pd.DataFrame(rows)
