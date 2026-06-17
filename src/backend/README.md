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
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or from `src/backend/scripts/`:

```powershell
.\run_dev.ps1
```

Restart the server manually after code changes. We do not use `--reload`: each chat turn writes `data/experiment.db`, which used to restart uvicorn mid-session and drop WebSocket + TTS.

Research dashboard (same backend process / Docker container as the WebSocket API):

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/research/dashboard` | HTML: summary figures, **behavioral profiles** table, chat sessions table, detail modals, delete controls |
| `http://127.0.0.1:8000/research/figures` | JSON: avg messages/session, avg session duration |
| `http://127.0.0.1:8000/research/stats` | JSON: session / participant / turn totals |
| `http://127.0.0.1:8000/research/profiles` | JSON: profile index (raw, YAML, validation, refinement metadata) |
| `http://127.0.0.1:8000/research/profiles/stats` | JSON: profile totals (count, YAML, validation passed) |
| `http://127.0.0.1:8000/research/profiles/{profile_id}` | JSON: full profile detail for one ID |
| `http://127.0.0.1:8000/research/sessions` | JSON: session index |
| `http://127.0.0.1:8000/research/sessions/{session_id}/turns` | JSON: full message log for one session |

From the dashboard UI you can **delete a single profile** (row button or profile modal), **delete all profiles**, **delete a single chat session** (row button or session modal), or **delete all session data** (with confirmation). JSON delete endpoints: `DELETE /research/profiles/{profile_id}`, `DELETE /research/profiles`, `DELETE /research/sessions/{session_id}`, and `DELETE /research/data`.

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
| POST | `/profiles/interview/start` | Start calibration-cycle profile training |
| POST | `/profiles/interview/turn` | Answer a probe question (2–3 per cycle) |
| POST | `/profiles/interview/verdict` | Accept imitation (`accept`) or send correction (`refine` + message) |
| POST | `/profiles/interview/finish` | Participant satisfied — unlock save (min 2 cycles) |
| POST | `/profiles/interview/save` | Extract YAML profile from samples and persist |
| GET | `/profiles` | List trained profile IDs |
| GET | `/profiles/behavioral/{profile_id}` | Load compiled profile |
| POST | `/profiles/validation/generate-sample` | Sample reply using profile (condition A prompt) |
| POST | `/profiles/validation` | Save validator ratings |
| POST | `/profiles/validation/ai-judge` | LLM scores a sample (`validator_id=ai-judge`) |
| POST | `/profiles/validation/auto-test` | Generate + AI-judge N samples (optional finalize) |
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

## LangGraph agents & skills

Two conversational agents drive the backend. Instructions and profiles are loaded from **Cursor-style skills** (`skills/<id>/skill.yaml`) and rendered with **Jinja2** (`app/prompts/templates/`).

| Agent | Module | Skill | Used by |
|-------|--------|-------|---------|
| **Training** | `training_agent.py` | `train_profile` | `POST /profiles/training/*` |
| **Conversation** | `conversation_agent.py` | `converse_with_profile` | WebSocket turns, `POST /experiment/chat`, validation sample gen, refinement chat |

Supporting graphs (not full agents):

| Graph | Module | HTTP |
|-------|--------|------|
| Profile refinement | `refinement_graph.py` | `POST /profiles/refinement/*` |
| Pilot validation | `validation_graph.py` | `POST /profiles/validation/*` |

Message history uses LangGraph-style trimming (`app/agents/memory.py`): system prompt + last N turns from SQLite (WS) or client history (HTTP).

Storage under `data/profiles/` (gitignored):

```
raw/{profile_id}.json
behavioral/{profile_id}.yaml
behavioral/{profile_id}.json   # style_summary mirror
refinement/{profile_id}.json
validation/{profile_id}.json
sessions/{profile_id}_{phase}.json
```

Legacy `/profiles/interview/*` routes delegate to the training graph.

Smoke tests:

```bash
uv run python scripts/smoke_profile_workflow.py
uv run python scripts/smoke_langgraph_agents.py
```

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

Docker and lab setup: [README principal](../../README.md).

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
