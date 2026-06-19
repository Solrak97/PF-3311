# Prototipo técnico (`src/`)

**Inicio rápido (Docker + Godot):** ver [README principal](../README.md).

**Demo en video:** [YouTube](https://youtu.be/jj2V7gkvOVU)

Contexto del estudio, diseño experimental y documentación extendida: mismo README y `docs/`.

## Layout

| Path | Role |
|------|------|
| [`familiar_godot/`](familiar_godot/) | Godot 4.6 client — naivee VRM avatar, WebSocket, chat UI |
| [`backend/`](backend/) | Python FastAPI — Ollama stream, Edge-TTS, SQLite logging, research dashboard |
| [`analysis/`](analysis/) | Notebooks, informes, exportaciones y figuras del análisis experimental |

## Run the buddy (dev)

1. **Ollama** — install and run locally, then pull a model (example):

   `ollama pull llama3.2`

2. **Backend** — from `src/backend/` ([uv](https://docs.astral.sh/uv/)):

   ```bash
   uv sync
   copy .env.example .env
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   **Research dashboard:** `http://127.0.0.1:8000/research/dashboard`  
   Session/message logs, summary figures, per-session delete, and wipe-all. Data file: `src/backend/data/experiment.db` (gitignored).

3. **Godot** — open `src/familiar_godot/project.godot`, run from `scenes/experiment/ExperimentMenu.tscn` (F5).

   - Set **Participant ID** and **Order** (A-B / B-A) on the menu before each participant.
   - Default WebSocket: `ws://127.0.0.1:8000/ws/session` (override via **Backend Ws** or env `FAMILIAR_BACKEND_WS`).

Configure the LLM in `src/backend/.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`; see `.env.example`). Local Ollama needs no API key.

Requires network for **Edge-TTS**. Whisper / mic endpointing are wired as libraries for a later milestone; the current loop is **typed text → Ollama → animation JSON → MP3**.

## Docker shortcut

From repo root:

```bash
docker compose up --build -d
docker exec -it pf3311-ollama ollama pull llama3.1:latest
```

Dashboard on the same port: `http://127.0.0.1:8000/research/dashboard`. SQLite persists in Docker volume `backend_data`.

Lab export and multi-machine setup: [README principal](../README.md) (secciones Docker y export Godot).
