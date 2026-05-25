# Prototipo técnico (`src/`)

Contexto del estudio PF-3311, diseño experimental y documentación: ver [README principal](../README.md).

## Layout

| Path | Role |
|------|------|
| [`familiar_godot/`](familiar_godot/) | Godot 4.6 client — UI, WebSocket, audio playback |
| [`backend/`](backend/) | Python FastAPI service — Ollama chat stream, Edge-TTS |

## Run the buddy (dev)

1. **Ollama** — install and run locally, then pull a model (example):

   `ollama pull llama3.2`

2. **Backend** — from `src/backend/` ([uv](https://docs.astral.sh/uv/)):

   ```bash
   uv sync
   copy .env.example .env
   uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

3. **Godot** — open `src/familiar_godot/project.godot`, run the main scene. It connects to `ws://127.0.0.1:8000/ws/session` by default (override on the root `Main` node via **Backend Ws** export if needed).

Requires network for **Edge-TTS**. Whisper / mic endpointing are wired as libraries and modules for the next milestone; the current loop is **typed text → Ollama → optional animation JSON → MP3**.
