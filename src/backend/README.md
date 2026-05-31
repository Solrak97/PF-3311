# Backend (PF-3311)

WebSocket API for the Godot client: Ollama chat streaming, Edge-TTS audio, optional Whisper STT. Persists experiment turns and session metadata in SQLite for the research dashboard.
Uses [uv](https://docs.astral.sh/uv/) for the virtualenv and dependencies.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then from this directory:

```bash
cd src/backend
uv sync
copy .env.example .env
```

`uv sync` creates `.venv` and installs locked dependencies from `uv.lock`.

## Run

Requires [Ollama](https://ollama.com/) running locally with your chosen model pulled (e.g. `ollama pull llama3.2`).

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --reload-exclude "data/*" --reload-exclude "*.db"
```

Or from `src/backend/scripts/`:

```powershell
.\run_dev.ps1
```

**WebSocket drops during dev?** `--reload` restarts the server when files change. Each turn writes to `data/experiment.db`, which used to trigger a restart and close open WS connections. The excludes above fix that. For a stable session, run without reload: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.

Research dashboard (same backend process / Docker container as the WebSocket API):

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/research/dashboard` | HTML: summary figures, session table, click row → message modal, delete controls |
| `http://127.0.0.1:8000/research/figures` | JSON: avg messages/session, avg session duration |
| `http://127.0.0.1:8000/research/stats` | JSON: session / participant / turn totals |
| `http://127.0.0.1:8000/research/sessions` | JSON: session index |
| `http://127.0.0.1:8000/research/sessions/{session_id}/turns` | JSON: full message log for one session |

From the dashboard UI you can **delete a single session** (row button or modal) or **delete all data** (with confirmation). JSON delete endpoints: `DELETE /research/sessions/{session_id}` and `DELETE /research/data`.

### Data storage

All logged data lives in SQLite (`SQLITE_PATH`, default `./data/experiment.db`; Docker: `/app/data/experiment.db` on volume `backend_data`):

| Table | Contents |
|-------|----------|
| `turns` | Participant message, agent reply, condition, order group, timestamps |
| `sessions` | Session start/end, client timer duration, message counts |

The file is gitignored (`src/backend/data/*.db`). To wipe manually: stop the backend and delete the file, or use the dashboard **Delete all data** button.

Godot sends `session.end` with elapsed timer seconds when the timer expires, the user opens the menu, starts **New chat**, or quits. Set **Participant ID** and **Order** (A-B / B-A) on the Godot menu before each run.

LLM context uses **only turns from the current `session_id`** (no carry-over). Each **Start Chat A/B** or **New chat** generates a new `session_id`. Turns with a missing/empty `session_id` are rejected.

## Profiles and skills (experiment)

Committed scaffolding (runtime data is gitignored under `data/profiles/`):

```
profiles/
  README.md
  generic_control_agent.yaml
  schema/raw_profile.schema.json
  schema/behavioral_profile.schema.json
skills/
  README.md
  retrieve_context.json
data/profiles/          # runtime (gitignored)
  raw/{profile_id}.json
  behavioral/{profile_id}.json
  validation/{validator_id}_{timestamp}.json
```

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/profiles/raw` | Save training samples → compile behavioral profile |
| POST | `/profiles/interview/start` | Start LLM profile-training interview |
| POST | `/profiles/interview/turn` | Submit answer / skip → next interviewer question |
| POST | `/profiles/interview/save` | Persist interview samples as raw + behavioral profile |
| GET | `/profiles` | List trained profile IDs |
| GET | `/profiles/behavioral/{profile_id}` | Load compiled profile |
| POST | `/profiles/validation/generate-sample` | Sample reply using profile (condition A prompt) |
| POST | `/profiles/validation` | Save validator ratings |
| POST | `/experiment/chat` | Optional HTTP chat mirror (primary run path is WebSocket) |

### WebSocket experiment fields

On `turn.user_text` (and related session payloads), the Godot experiment run may include:

| Field | Purpose |
|-------|---------|
| `experiment_mode: true` | Enable profile-aware prompt path |
| `profile_id` | Trained behavioral profile for condition A; B logs as `generic_control_agent` |
| `interaction_index` | 1 or 2 (counterbalanced order) |

Condition **A**: load trained Profile A + skills retrieval stub when `profile_id` is sent.  
Condition **B**: always load committed `profiles/generic_control_agent.yaml` — no familiarity prompting, no profile-specific retrieval (`retrieval_used=false`).  
If no profile path applies, the generic spoken Buddy prompt is used (dev fallback).

SQLite `turns` table also stores `profile_id` and `interaction_index` when present.

Config (`app/config.py`): `PROFILES_DATA_DIR`, `SKILLS_DIR`, `EXPERIMENT_INTERACTION_SEC` (default 300).

## Environment

See [.env.example](.env.example). Primary knobs for shipping:

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `ollama` (default) or `openai_compat` |
| `LLM_BASE_URL` | API root (`http://127.0.0.1:11434`, Docker `http://ollama:11434`, or cloud URL) |
| `LLM_MODEL` | Model name |
| `LLM_API_KEY` | Bearer token when using remote OpenAI-compatible APIs |

`OLLAMA_BASE_URL` / `OLLAMA_MODEL` still work as fallbacks if `LLM_*` are unset.

| Variable | Purpose |
|----------|---------|
| `EDGE_TTS_VOICE` | Microsoft neural voice id (default `en-US-AriaNeural`) |

### TTS voice (Edge)

Set `EDGE_TTS_VOICE` in `.env` and restart the backend. List US English options:

```bash
uv run python scripts/list_edge_voices.py en-US
```

Generate short MP3 previews to compare (written under `data/voice_previews/`):

```bash
uv run python scripts/preview_edge_voices.py
uv run python scripts/preview_edge_voices.py en-US-GuyNeural en-US-AnaNeural
```

Buddy-friendly `en-US` picks to try: **Ana** (lighter), **Jenny** (chatty), **Guy** / **Eric** / **Christopher** (warm male), **Brian** (upbeat). **Aria** (default) is clearer but more “assistant” than companion.

Full shipping layout: [`docs/DEPLOY.md`](../../docs/DEPLOY.md).

## Dependencies

Edit `pyproject.toml`, then refresh the lockfile:

```bash
uv lock
uv sync
```

## Docker (backend + Ollama)

From repository root:

```bash
docker compose up --build -d
```

Then pull model once:

```bash
docker exec -it pf3311-ollama ollama pull llama3.1:latest
```

Backend: `http://127.0.0.1:8000`  
Dashboard: `http://127.0.0.1:8000/research/dashboard`
