from __future__ import annotations

from datetime import datetime
from html import escape

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.profiles.store import ProfileStore
from app.storage.sqlite_store import SQLiteExperimentStore

_CSS = """
body { font-family: system-ui, Arial, sans-serif; margin: 24px; color: #1f2430; background: #f6f7f9; }
a { color: #0b63ce; text-decoration: none; }
h1 { margin: 0 0 4px; font-size: 1.6rem; }
h2 { margin: 0 0 12px; font-size: 1.05rem; }
.hint { color: #555; margin-bottom: 20px; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; }
.card {
  background: #fff; border: 1px solid #e2e4e8; border-radius: 10px;
  padding: 14px 18px; min-width: 140px;
}
.card .label { font-size: 0.78rem; color: #666; text-transform: uppercase; letter-spacing: 0.04em; }
.card .value { font-size: 1.5rem; font-weight: 700; margin-top: 4px; }
.card .sub { font-size: 0.78rem; color: #777; margin-top: 4px; }
.panel {
  background: #fff; border: 1px solid #e2e4e8; border-radius: 10px;
  padding: 16px; margin-bottom: 20px; overflow-x: auto;
}
table { border-collapse: collapse; width: 100%; font-size: 0.92rem; }
th, td { border: 1px solid #e2e4e8; padding: 8px 10px; text-align: left; vertical-align: top; }
th { background: #f0f1f4; font-weight: 600; }
tr:nth-child(even) td { background: #fafbfc; }
tr.session-row { cursor: pointer; }
tr.session-row:hover td { background: #eef3ff; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.btn {
  border: 1px solid #d8dbe0; background: #fff; border-radius: 8px;
  padding: 6px 12px; cursor: pointer; font-size: 0.88rem;
}
.btn:hover { background: #f6f7f9; }
.btn-danger { border-color: #efb8b8; color: #9b1c1c; background: #fff5f5; }
.btn-danger:hover { background: #ffe8e8; }
.btn-sm { padding: 4px 8px; font-size: 0.8rem; }
.actions { width: 88px; text-align: center; white-space: nowrap; }
.modal-actions { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 0.85rem; word-break: break-all; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  background: #eef3ff; color: #1a4fb3; font-size: 0.8rem; font-weight: 600;
}
.empty { color: #777; font-style: italic; }
.modal-backdrop {
  display: none; position: fixed; inset: 0; background: rgba(15, 18, 24, 0.45);
  align-items: center; justify-content: center; padding: 24px; z-index: 1000;
}
.modal-backdrop.open { display: flex; }
.modal {
  background: #fff; border-radius: 12px; width: min(920px, 100%);
  max-height: 85vh; display: flex; flex-direction: column;
  box-shadow: 0 16px 48px rgba(0,0,0,0.18);
}
.modal-head {
  display: flex; justify-content: space-between; align-items: start; gap: 12px;
  padding: 16px 18px; border-bottom: 1px solid #e2e4e8;
}
.modal-body { padding: 0 18px 18px; overflow: auto; }
.modal-meta { display: flex; flex-wrap: wrap; gap: 8px 16px; color: #555; font-size: 0.88rem; margin-top: 6px; }
.modal-close {
  border: 1px solid #d8dbe0; background: #fff; border-radius: 8px;
  padding: 6px 12px; cursor: pointer; font-size: 0.9rem;
}
.msg { border: 1px solid #e8eaee; border-radius: 10px; padding: 10px 12px; margin-top: 10px; }
.msg .who { font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }
.msg.user .who { color: #1a4fb3; }
.msg.agent .who { color: #2d6a4f; }
.msg .when { color: #888; font-size: 0.78rem; margin-left: 8px; font-weight: 400; }
.msg .text { white-space: pre-wrap; line-height: 1.45; }
"""


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_dt(value: str) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return escape(value or "—")
    return escape(dt.strftime("%Y-%m-%d %H:%M:%S UTC"))


def _format_duration(started: str, ended: str) -> str:
    start = _parse_iso(started)
    end = _parse_iso(ended)
    if start is None or end is None:
        return "—"
    secs = max(0, int((end - start).total_seconds()))
    if secs < 60:
        return f"{secs}s"
    minutes, seconds = divmod(secs, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _format_duration_sec(secs: int | None) -> str:
    if secs is None:
        return "—"
    secs = max(0, int(secs))
    if secs < 60:
        return f"{secs}s"
    minutes, seconds = divmod(secs, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


def _session_duration_label(session: dict) -> str:
    if session.get("duration_sec") is not None:
        return _format_duration_sec(int(session["duration_sec"]))
    return _format_duration(str(session.get("started_at", "")), str(session.get("last_turn_at", "")))


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def _stats_cards(stats: dict, figures: dict, profile_stats: dict | None = None) -> str:
    profile_stats = profile_stats or {}
    return f"""
<div class="cards">
  <div class="card"><div class="label">Sessions</div><div class="value">{stats.get('sessions', 0)}</div></div>
  <div class="card"><div class="label">Participants</div><div class="value">{stats.get('participants', 0)}</div></div>
  <div class="card"><div class="label">Messages logged</div><div class="value">{stats.get('turns', 0)}</div></div>
  <div class="card">
    <div class="label">Avg messages / session</div>
    <div class="value">{figures.get('avg_messages_per_session', 0)}</div>
  </div>
  <div class="card">
    <div class="label">Avg session time</div>
    <div class="value">{escape(str(figures.get('avg_duration_label', '—')))}</div>
    <div class="sub">{figures.get('sessions_with_duration', 0)} sessions with timer data</div>
  </div>
  <div class="card"><div class="label">Profiles</div><div class="value">{profile_stats.get('profiles', 0)}</div></div>
  <div class="card"><div class="label">YAML profiles</div><div class="value">{profile_stats.get('with_yaml', 0)}</div></div>
  <div class="card"><div class="label">Validation passed</div><div class="value">{profile_stats.get('validation_passed', 0)}</div></div>
</div>"""


def _session_index_rows(sessions: list[dict]) -> str:
    if not sessions:
        return (
            "<tr><td colspan='9' class='empty'>No data yet — start a chat in Godot "
            "with a participant ID set on the menu.</td></tr>"
        )
    rows: list[str] = []
    for s in sessions:
        sid = escape(str(s["session_id"]))
        sid_js = sid.replace("'", "\\'")
        duration = _session_duration_label(s)
        turns = int(s.get("turns") or 0)
        rows.append(
            f"<tr class='session-row' data-session-id='{sid}'>"
            f"<td class='mono' onclick='openSession(\"{sid_js}\")'>{sid}</td>"
            f"<td class='mono' onclick='openSession(\"{sid_js}\")'>{escape(str(s['participant_id']))}</td>"
            f"<td onclick='openSession(\"{sid_js}\")'><span class='badge'>{escape(str(s.get('conditions') or '—'))}</span></td>"
            f"<td onclick='openSession(\"{sid_js}\")'>{escape(str(s.get('order_groups') or '—'))}</td>"
            f"<td onclick='openSession(\"{sid_js}\")'>{turns}</td>"
            f"<td onclick='openSession(\"{sid_js}\")'>{escape(duration)}</td>"
            f"<td onclick='openSession(\"{sid_js}\")'>{_format_dt(str(s.get('started_at', '')))}</td>"
            f"<td onclick='openSession(\"{sid_js}\")'>{_format_dt(str(s.get('last_turn_at', '')))}</td>"
            f"<td class='actions'>"
            f"<button type='button' class='btn btn-danger btn-sm' "
            f"onclick='event.stopPropagation(); deleteSession(\"{sid_js}\")'>Delete</button>"
            f"</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _validation_badge(passed: bool | None) -> str:
    if passed is True:
        return "<span class='badge' style='background:#e8f5e9;color:#2d6a4f'>passed</span>"
    if passed is False:
        return "<span class='badge' style='background:#fff5f5;color:#9b1c1c'>not passed</span>"
    return "<span class='badge'>—</span>"


def _profile_index_rows(profiles: list[dict]) -> str:
    if not profiles:
        return (
            "<tr><td colspan='9' class='empty'>No profiles yet — train one under "
            "Experimental Setup → Train Profile.</td></tr>"
        )
    rows: list[str] = []
    for p in profiles:
        pid = escape(str(p.get("profile_id", "")))
        pid_js = pid.replace("'", "\\'")
        alias = escape(str(p.get("modeled_user_alias") or "—"))
        yaml_mark = "yes" if p.get("has_behavioral_yaml") else "—"
        refinement = "yes" if p.get("has_refinement") else "—"
        sessions = ", ".join(p.get("active_sessions") or []) or "—"
        rows.append(
            f"<tr class='session-row' data-profile-id='{pid}'>"
            f"<td class='mono' onclick='openProfile(\"{pid_js}\")'>{pid}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{alias}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{int(p.get('sample_count') or 0)}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{escape(yaml_mark)}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{_validation_badge(p.get('validation_passed'))}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{escape(refinement)}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{escape(sessions)}</td>"
            f"<td onclick='openProfile(\"{pid_js}\")'>{_format_dt(str(p.get('created_at', '')))}</td>"
            f"<td class='actions'>"
            f"<button type='button' class='btn btn-danger btn-sm' "
            f"onclick='event.stopPropagation(); deleteProfile(\"{pid_js}\")'>Delete</button>"
            f"</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _render_index(store: SQLiteExperimentStore, profile_store: ProfileStore | None, limit: int) -> str:
    stats = store.stats()
    figures = store.session_figures()
    sessions = store.list_sessions(limit=limit)
    profile_stats = profile_store.profile_stats() if profile_store else {}
    profiles = profile_store.list_profiles_detail() if profile_store else []
    body = f"""
<h1>PF-3311 Research Dashboard</h1>
<p class="hint">Session logs from experiment runs and behavioral profiles from training/validation. Click a row to inspect details.</p>
{_stats_cards(stats, figures, profile_stats)}
<div class="panel">
  <div class="toolbar">
    <h2>Behavioral profiles</h2>
    <button type="button" class="btn btn-danger" onclick="deleteAllProfiles()">Delete all profiles</button>
  </div>
  <table>
    <thead>
      <tr>
        <th>Profile ID</th>
        <th>Alias</th>
        <th>Samples</th>
        <th>YAML</th>
        <th>Validation</th>
        <th>Refinement</th>
        <th>Active sessions</th>
        <th>Created (UTC)</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {_profile_index_rows(profiles)}
    </tbody>
  </table>
</div>
<div class="panel">
  <div class="toolbar">
    <h2>Chat sessions</h2>
    <button type="button" class="btn btn-danger" onclick="deleteAllData()">Delete all session data</button>
  </div>
  <table>
    <thead>
      <tr>
        <th>Session</th>
        <th>Participant</th>
        <th>Condition</th>
        <th>Order</th>
        <th>Messages</th>
        <th>Duration</th>
        <th>Started (UTC)</th>
        <th>Last message (UTC)</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {_session_index_rows(sessions)}
    </tbody>
  </table>
</div>
<div id="modal" class="modal-backdrop" onclick="if(event.target===this) closeModal()">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head">
      <div>
        <h2 id="modal-title">Session log</h2>
        <div id="modal-meta" class="modal-meta"></div>
      </div>
      <div class="modal-actions">
        <button type="button" id="modal-delete" class="btn btn-danger" style="display:none" onclick="deleteCurrentSession()">Delete session</button>
        <button type="button" class="btn modal-close" onclick="closeModal()">Close</button>
      </div>
    </div>
    <div class="modal-body">
      <div id="modal-messages"></div>
    </div>
  </div>
</div>
<div id="profile-modal" class="modal-backdrop" onclick="if(event.target===this) closeProfileModal()">
  <div class="modal" role="dialog" aria-modal="true">
    <div class="modal-head">
      <div>
        <h2 id="profile-modal-title">Profile</h2>
        <div id="profile-modal-meta" class="modal-meta"></div>
      </div>
      <div class="modal-actions">
        <button type="button" id="profile-modal-delete" class="btn btn-danger" style="display:none" onclick="deleteCurrentProfile()">Delete profile</button>
        <button type="button" class="btn modal-close" onclick="closeProfileModal()">Close</button>
      </div>
    </div>
    <div class="modal-body">
      <div id="profile-modal-body"></div>
    </div>
  </div>
</div>
<script>
let currentSessionId = null;
let currentProfileId = null;

function esc(s) {{
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}
function fmtDuration(secs) {{
  if (secs == null) return '—';
  secs = Math.max(0, parseInt(secs, 10) || 0);
  if (secs < 60) return secs + 's';
  const m = Math.floor(secs / 60), s = secs % 60;
  if (m < 60) return m + 'm ' + s + 's';
  const h = Math.floor(m / 60), rm = m % 60;
  return h + 'h ' + rm + 'm';
}}
async function openSession(sessionId) {{
  currentSessionId = sessionId;
  const modal = document.getElementById('modal');
  const title = document.getElementById('modal-title');
  const meta = document.getElementById('modal-meta');
  const messages = document.getElementById('modal-messages');
  const deleteBtn = document.getElementById('modal-delete');
  deleteBtn.style.display = 'inline-block';
  title.textContent = 'Loading…';
  meta.textContent = '';
  messages.innerHTML = '<p class="empty">Loading messages…</p>';
  modal.classList.add('open');
  try {{
    const [turnsRes, sessionsRes] = await Promise.all([
      fetch('/research/sessions/' + encodeURIComponent(sessionId) + '/turns'),
      fetch('/research/sessions?limit=500'),
    ]);
    const turns = await turnsRes.json();
    const sessions = await sessionsRes.json();
    const session = sessions.find(s => s.session_id === sessionId) || {{}};
    title.textContent = sessionId;
    const dur = session.duration_sec != null
      ? fmtDuration(session.duration_sec) + ' (client timer)'
      : '—';
    meta.innerHTML = [
      'Participant: <span class="mono">' + esc(session.participant_id || '—') + '</span>',
      'Messages: ' + esc(String(turns.length)),
      'Duration: ' + esc(dur),
      'Condition: ' + esc(session.conditions || '—'),
      'Order: ' + esc(session.order_groups || '—'),
    ].join(' · ');
    if (!turns.length) {{
      messages.innerHTML = '<p class="empty">No messages logged for this session.</p>';
      return;
    }}
    messages.innerHTML = turns.map(t => {{
      const when = esc((t.created_at || '').replace('T', ' ').replace('+00:00', ' UTC'));
      const user = esc(t.user_text || '');
      const agent = esc(t.assistant_text || '');
      return (
        '<div class="msg user"><div class="who">Participant<span class="when">' + when + '</span></div>'
        + '<div class="text">' + (user || '—') + '</div></div>'
        + '<div class="msg agent"><div class="who">Agent</div>'
        + '<div class="text">' + (agent || '—') + '</div></div>'
      );
    }}).join('');
  }} catch (err) {{
    messages.innerHTML = '<p class="empty">Failed to load messages.</p>';
    console.error(err);
  }}
}}
function closeModal() {{
  currentSessionId = null;
  document.getElementById('modal-delete').style.display = 'none';
  document.getElementById('modal').classList.remove('open');
}}
async function deleteSession(sessionId) {{
  if (!confirm('Delete this session and all of its messages? This cannot be undone.')) return;
  const res = await fetch('/research/sessions/' + encodeURIComponent(sessionId), {{ method: 'DELETE' }});
  if (!res.ok) {{
    alert('Could not delete session.');
    return;
  }}
  if (currentSessionId === sessionId) closeModal();
  location.reload();
}}
async function deleteCurrentSession() {{
  if (!currentSessionId) return;
  await deleteSession(currentSessionId);
}}
async function deleteAllData() {{
  if (!confirm('Delete ALL logged chat sessions and messages? This cannot be undone.')) return;
  if (!confirm('Really delete all session data in the research database?')) return;
  const res = await fetch('/research/data', {{ method: 'DELETE' }});
  if (!res.ok) {{
    alert('Could not delete session data.');
    return;
  }}
  closeModal();
  location.reload();
}}
async function openProfile(profileId) {{
  currentProfileId = profileId;
  const modal = document.getElementById('profile-modal');
  const title = document.getElementById('profile-modal-title');
  const meta = document.getElementById('profile-modal-meta');
  const body = document.getElementById('profile-modal-body');
  const deleteBtn = document.getElementById('profile-modal-delete');
  deleteBtn.style.display = 'inline-block';
  title.textContent = 'Loading…';
  meta.textContent = '';
  body.innerHTML = '<p class="empty">Loading profile…</p>';
  modal.classList.add('open');
  try {{
    const res = await fetch('/research/profiles/' + encodeURIComponent(profileId));
    if (!res.ok) throw new Error('not found');
    const data = await res.json();
    title.textContent = profileId;
    const files = data.files || {{}};
    meta.innerHTML = [
      'Raw: ' + (files.raw ? 'yes' : 'no'),
      'YAML: ' + (files.behavioral_yaml ? 'yes' : 'no'),
      'Refinement: ' + (files.refinement ? 'yes' : 'no'),
      'Validation records: ' + esc(String(files.validation_records || 0)),
    ].join(' · ');
    const raw = data.raw || {{}};
    const behavioral = data.behavioral || {{}};
    const validation = data.validation || {{}};
    const summary = validation.summary || {{}};
    const style = esc(behavioral.style_summary || '(no style summary)');
    const samples = Array.isArray(raw.samples) ? raw.samples.length : 0;
    body.innerHTML = (
      '<div class="msg"><div class="who">Overview</div><div class="text">'
      + 'Alias: ' + esc(raw.modeled_user_alias || behavioral.modeled_user_alias || '—') + '\\n'
      + 'Training samples: ' + samples + '\\n'
      + 'Validation passed: ' + esc(String(summary.passed ?? '—')) + '\\n'
      + 'Mean similarity: ' + esc(String(summary.mean_similarity ?? '—'))
      + '</div></div>'
      + '<div class="msg agent"><div class="who">Style summary</div><div class="text">' + style + '</div></div>'
    );
  }} catch (err) {{
    body.innerHTML = '<p class="empty">Failed to load profile.</p>';
    console.error(err);
  }}
}}
function closeProfileModal() {{
  currentProfileId = null;
  document.getElementById('profile-modal-delete').style.display = 'none';
  document.getElementById('profile-modal').classList.remove('open');
}}
async function deleteProfile(profileId) {{
  if (!confirm('Delete profile "' + profileId + '" and all related files (raw, YAML, validation, refinement, sessions)?')) return;
  const res = await fetch('/research/profiles/' + encodeURIComponent(profileId), {{ method: 'DELETE' }});
  if (!res.ok) {{
    alert('Could not delete profile.');
    return;
  }}
  if (currentProfileId === profileId) closeProfileModal();
  location.reload();
}}
async function deleteCurrentProfile() {{
  if (!currentProfileId) return;
  await deleteProfile(currentProfileId);
}}
async function deleteAllProfiles() {{
  if (!confirm('Delete ALL behavioral profiles and related files?')) return;
  if (!confirm('This removes raw samples, YAML profiles, validation, and refinement data. Continue?')) return;
  const res = await fetch('/research/profiles', {{ method: 'DELETE' }});
  if (!res.ok) {{
    alert('Could not delete profiles.');
    return;
  }}
  closeProfileModal();
  location.reload();
}}
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') {{ closeModal(); closeProfileModal(); }}
}});
</script>
"""
    return _page("PF-3311 Research Dashboard", body)


def build_dashboard_router(
    store: SQLiteExperimentStore,
    profile_store: ProfileStore | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/research", tags=["research"])

    @router.get("/profiles")
    async def list_profiles() -> list[dict]:
        if profile_store is None:
            return []
        return profile_store.list_profiles_detail()

    @router.get("/profiles/stats")
    async def profile_stats() -> dict:
        if profile_store is None:
            return {"profiles": 0, "with_yaml": 0, "with_validation": 0, "validation_passed": 0}
        return profile_store.profile_stats()

    @router.get("/profiles/{profile_id}")
    async def get_profile(profile_id: str) -> dict:
        if profile_store is None:
            raise HTTPException(status_code=503, detail="profile_store_unavailable")
        try:
            detail = profile_store.get_profile_detail(profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if detail is None:
            raise HTTPException(status_code=404, detail="profile_not_found")
        return detail

    @router.delete("/profiles/{profile_id}")
    async def delete_profile(profile_id: str) -> dict:
        if profile_store is None:
            raise HTTPException(status_code=503, detail="profile_store_unavailable")
        try:
            return profile_store.delete_profile(profile_id.strip())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.delete("/profiles")
    async def delete_all_profiles() -> dict:
        if profile_store is None:
            raise HTTPException(status_code=503, detail="profile_store_unavailable")
        return profile_store.delete_all_profiles()

    @router.get("/stats")
    async def stats() -> dict:
        return store.stats()

    @router.get("/figures")
    async def figures() -> dict:
        return store.session_figures()

    @router.get("/sessions")
    async def sessions(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
        return store.list_sessions(limit=limit)

    @router.get("/sessions/{session_id}/turns")
    async def session_turns(session_id: str) -> list[dict]:
        return store.list_turns_for_session(session_id=session_id)

    @router.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict:
        session_id = session_id.strip()
        if not session_id:
            raise HTTPException(status_code=400, detail="missing_session_id")
        result = store.delete_session(session_id=session_id)
        if result["turns_deleted"] == 0 and result["sessions_deleted"] == 0:
            raise HTTPException(status_code=404, detail="session_not_found")
        return result

    @router.delete("/data")
    async def delete_all_data() -> dict:
        return store.delete_all_data()

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard(limit: int = Query(default=200, ge=1, le=500)) -> str:
        return _render_index(store, profile_store, limit)

    return router
