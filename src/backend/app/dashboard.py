from __future__ import annotations

from html import escape

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.storage.sqlite_store import SQLiteExperimentStore


def build_dashboard_router(store: SQLiteExperimentStore) -> APIRouter:
    router = APIRouter(prefix="/research", tags=["research"])

    @router.get("/sessions")
    async def sessions(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
        return store.list_sessions(limit=limit)

    @router.get("/sessions/{session_id}/turns")
    async def session_turns(session_id: str) -> list[dict]:
        return store.list_turns_for_session(session_id=session_id)

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> str:
        sessions = store.list_sessions(limit=200)
        rows = []
        for s in sessions:
            sid = escape(str(s["session_id"]))
            rows.append(
                "<tr>"
                f"<td><a href='/research/dashboard?session_id={sid}'>{sid}</a></td>"
                f"<td>{escape(str(s['participant_id']))}</td>"
                f"<td>{escape(str(s['turns']))}</td>"
                f"<td>{escape(str(s['conditions'] or ''))}</td>"
                f"<td>{escape(str(s['last_turn_at']))}</td>"
                "</tr>"
            )
        table = "\n".join(rows) if rows else "<tr><td colspan='5'>No data yet</td></tr>"
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>PF-3311 Research Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    a {{ color: #0b63ce; text-decoration: none; }}
    h1 {{ margin-bottom: 8px; }}
    .hint {{ color: #555; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <h1>PF-3311 Research Dashboard</h1>
  <div class="hint">Session index (SQLite). For raw turn data use API endpoints.</div>
  <table>
    <thead>
      <tr>
        <th>Session ID</th>
        <th>Participant</th>
        <th>Turns</th>
        <th>Conditions</th>
        <th>Last Turn</th>
      </tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
</body>
</html>"""

    return router
