from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def insert_turn(self, record: TurnRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO turns (
                    participant_id, session_id, condition, order_group, turn_index,
                    user_text, assistant_text, profile_used, retrieval_used, model_name,
                    audio_error_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    session_id,
                    participant_id,
                    MIN(created_at) AS started_at,
                    MAX(created_at) AS last_turn_at,
                    COUNT(*) AS turns,
                    GROUP_CONCAT(DISTINCT condition) AS conditions
                FROM turns
                GROUP BY session_id, participant_id
                ORDER BY last_turn_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

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
        )
