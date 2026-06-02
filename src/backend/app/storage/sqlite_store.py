from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_seconds(secs: int) -> str:
    secs = max(0, secs)
    if secs < 60:
        return f"{secs}s"
    minutes, seconds = divmod(secs, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


@dataclass
class TurnRecord:
    participant_id: str
    session_id: str
    condition: str
    order_group: str
    turn_index: int
    user_text: str
    assistant_text: str
    profile_used: bool
    retrieval_used: bool
    model_name: str
    audio_error_count: int
    created_at: str
    profile_id: str = ""
    interaction_index: int = 0
    scenario_id: str = ""


class SQLiteExperimentStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    order_group TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    profile_used INTEGER NOT NULL,
                    retrieval_used INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    audio_error_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_session
                ON turns(session_id, turn_index);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_turns_participant
                ON turns(participant_id, created_at);
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    participant_id TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    order_group TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    duration_sec INTEGER,
                    message_count INTEGER NOT NULL DEFAULT 0,
                    end_reason TEXT
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_participant
                ON sessions(participant_id, started_at);
                """
            )
            self._migrate_turns_columns(conn)

    def _migrate_turns_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(turns)").fetchall()}
        if "profile_id" not in cols:
            conn.execute("ALTER TABLE turns ADD COLUMN profile_id TEXT NOT NULL DEFAULT ''")
        if "interaction_index" not in cols:
            conn.execute("ALTER TABLE turns ADD COLUMN interaction_index INTEGER NOT NULL DEFAULT 0")
        if "scenario_id" not in cols:
            conn.execute("ALTER TABLE turns ADD COLUMN scenario_id TEXT NOT NULL DEFAULT ''")

    def record_session_start(
        self,
        *,
        session_id: str,
        participant_id: str,
        condition: str,
        order_group: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, participant_id, condition, order_group, started_at, message_count
                ) VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (session_id, participant_id, condition, order_group, _utc_now_iso()),
            )

    def record_session_end(
        self,
        *,
        session_id: str,
        duration_sec: int | None = None,
        message_count: int | None = None,
        end_reason: str = "",
        participant_id: str = "unknown",
        condition: str = "B",
        order_group: str = "A-B",
    ) -> None:
        now = _utc_now_iso()
        with self._connect() as conn:
            turn_count = conn.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            logged_turns = int(turn_count["n"]) if turn_count else 0
            final_count = logged_turns if message_count is None else max(logged_turns, message_count)
            exists = conn.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, participant_id, condition, order_group, started_at, message_count
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, participant_id, condition, order_group, now, final_count),
                )
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = ?,
                    duration_sec = COALESCE(?, duration_sec),
                    message_count = ?,
                    end_reason = COALESCE(NULLIF(?, ''), end_reason)
                WHERE session_id = ?
                """,
                (now, duration_sec, final_count, end_reason, session_id),
            )

    def insert_turn(self, record: TurnRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, participant_id, condition, order_group, started_at, message_count
                ) VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(session_id) DO NOTHING
                """,
                (
                    record.session_id,
                    record.participant_id,
                    record.condition,
                    record.order_group,
                    record.created_at,
                ),
            )
            conn.execute(
                """
                INSERT INTO turns (
                    participant_id, session_id, condition, order_group, turn_index,
                    user_text, assistant_text, profile_used, retrieval_used, model_name,
                    audio_error_count, created_at, profile_id, interaction_index, scenario_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.participant_id,
                    record.session_id,
                    record.condition,
                    record.order_group,
                    record.turn_index,
                    record.user_text,
                    record.assistant_text,
                    int(record.profile_used),
                    int(record.retrieval_used),
                    record.model_name,
                    record.audio_error_count,
                    record.created_at,
                    record.profile_id,
                    record.interaction_index,
                    record.scenario_id,
                ),
            )
            conn.execute(
                """
                UPDATE sessions
                SET message_count = (
                    SELECT COUNT(*) FROM turns WHERE session_id = ?
                )
                WHERE session_id = ?
                """,
                (record.session_id, record.session_id),
            )

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                WITH turn_stats AS (
                    SELECT
                        session_id,
                        participant_id,
                        MIN(created_at) AS first_turn_at,
                        MAX(created_at) AS last_turn_at,
                        COUNT(*) AS turns,
                        GROUP_CONCAT(DISTINCT condition) AS conditions,
                        GROUP_CONCAT(DISTINCT order_group) AS order_groups
                    FROM turns
                    GROUP BY session_id, participant_id
                ),
                merged AS (
                    SELECT
                        COALESCE(s.session_id, ts.session_id) AS session_id,
                        COALESCE(s.participant_id, ts.participant_id) AS participant_id,
                        COALESCE(ts.first_turn_at, s.started_at) AS started_at,
                        COALESCE(s.ended_at, ts.last_turn_at, s.started_at) AS last_turn_at,
                        COALESCE(ts.turns, 0) AS turns,
                        COALESCE(ts.conditions, s.condition) AS conditions,
                        COALESCE(ts.order_groups, s.order_group) AS order_groups,
                        s.duration_sec,
                        s.end_reason
                    FROM sessions s
                    LEFT JOIN turn_stats ts ON ts.session_id = s.session_id
                    UNION
                    SELECT
                        ts.session_id,
                        ts.participant_id,
                        ts.first_turn_at,
                        ts.last_turn_at,
                        ts.turns,
                        ts.conditions,
                        ts.order_groups,
                        s.duration_sec,
                        s.end_reason
                    FROM turn_stats ts
                    LEFT JOIN sessions s ON s.session_id = ts.session_id
                    WHERE s.session_id IS NULL
                )
                SELECT
                    session_id,
                    participant_id,
                    started_at,
                    last_turn_at,
                    turns,
                    conditions,
                    order_groups,
                    duration_sec,
                    end_reason
                FROM merged
                ORDER BY COALESCE(last_turn_at, started_at) DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def session_figures(self) -> dict[str, Any]:
        sessions = self.list_sessions(limit=10_000)
        if not sessions:
            return {
                "avg_messages_per_session": 0.0,
                "avg_duration_sec": 0.0,
                "avg_duration_label": "—",
                "sessions_with_duration": 0,
            }
        total_turns = sum(int(s.get("turns") or 0) for s in sessions)
        avg_messages = total_turns / len(sessions)
        durations = [int(s["duration_sec"]) for s in sessions if s.get("duration_sec") is not None]
        avg_duration_sec = sum(durations) / len(durations) if durations else 0.0
        return {
            "avg_messages_per_session": round(avg_messages, 1),
            "avg_duration_sec": round(avg_duration_sec, 1),
            "avg_duration_label": _format_seconds(int(avg_duration_sec)) if durations else "—",
            "sessions_with_duration": len(durations),
        }

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    (
                        SELECT COUNT(*) FROM (
                            SELECT session_id FROM turns
                            UNION
                            SELECT session_id FROM sessions
                        )
                    ) AS sessions,
                    (
                        SELECT COUNT(*) FROM (
                            SELECT participant_id FROM turns
                            UNION
                            SELECT participant_id FROM sessions
                        )
                    ) AS participants,
                    (SELECT COUNT(*) FROM turns) AS turns
                """
            ).fetchone()
        return dict(row) if row else {"sessions": 0, "participants": 0, "turns": 0}

    def list_turns_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    participant_id, session_id, condition, order_group, turn_index,
                    user_text, assistant_text, profile_used, retrieval_used, model_name,
                    audio_error_count, created_at
                FROM turns
                WHERE session_id = ?
                ORDER BY turn_index ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_session(self, session_id: str) -> dict[str, int]:
        with self._connect() as conn:
            turns_row = conn.execute(
                "SELECT COUNT(*) AS n FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            turns_deleted = int(turns_row["n"]) if turns_row else 0
            conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
            session_result = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            sessions_deleted = int(session_result.rowcount)
        return {
            "session_id": session_id,
            "turns_deleted": turns_deleted,
            "sessions_deleted": sessions_deleted,
        }

    def delete_all_data(self) -> dict[str, int]:
        with self._connect() as conn:
            turns_row = conn.execute("SELECT COUNT(*) AS n FROM turns").fetchone()
            sessions_row = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
            turns_deleted = int(turns_row["n"]) if turns_row else 0
            sessions_deleted = int(sessions_row["n"]) if sessions_row else 0
            conn.execute("DELETE FROM turns")
            conn.execute("DELETE FROM sessions")
        return {
            "turns_deleted": turns_deleted,
            "sessions_deleted": sessions_deleted,
        }

    def recent_turns_for_session(self, session_id: str, limit: int = 8) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_text, assistant_text
                FROM turns
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    def recent_turns_for_participant(self, participant_id: str, limit: int = 8) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT user_text, assistant_text
                FROM turns
                WHERE participant_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (participant_id, limit),
            ).fetchall()
        items = [dict(row) for row in rows]
        items.reverse()
        return items

    @staticmethod
    def make_record(
        *,
        participant_id: str,
        session_id: str,
        condition: str,
        order_group: str,
        turn_index: int,
        user_text: str,
        assistant_text: str,
        profile_used: bool,
        retrieval_used: bool,
        model_name: str,
        audio_error_count: int,
        profile_id: str = "",
        interaction_index: int = 0,
        scenario_id: str = "",
    ) -> TurnRecord:
        return TurnRecord(
            participant_id=participant_id,
            session_id=session_id,
            condition=condition,
            order_group=order_group,
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            profile_used=profile_used,
            retrieval_used=retrieval_used,
            model_name=model_name,
            audio_error_count=audio_error_count,
            created_at=_utc_now_iso(),
            profile_id=profile_id,
            interaction_index=interaction_index,
            scenario_id=scenario_id,
        )
