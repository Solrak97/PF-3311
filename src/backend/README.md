# Familiar backend

WebSocket API for the Godot client: Ollama chat streaming, Edge-TTS audio, optional Whisper STT.

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

Research dashboard and APIs:

- `http://127.0.0.1:8000/research/dashboard`
- `http://127.0.0.1:8000/research/sessions`
- `http://127.0.0.1:8000/research/sessions/{session_id}/turns`

Turns are persisted in SQLite (`SQLITE_PATH`, default `./data/experiment.db`), keyed by `session_id` from the client. LLM context uses **only turns from the current session** (no carry-over from prior runs). Each Godot **Start Chat A/B** generates a new `session_id`.

## Environment

See [.env.example](.env.example). Primary knobs for shipping:

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `ollama` (default) or `openai_compat` |
| `LLM_BASE_URL` | API root (`http://127.0.0.1:11434`, Docker `http://ollama:11434`, or cloud URL) |
| `LLM_MODEL` | Model name |
| `LLM_API_KEY` | Bearer token when using remote OpenAI-compatible APIs |

`OLLAMA_BASE_URL` / `OLLAMA_MODEL` still work as fallbacks if `LLM_*` are unset.

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
