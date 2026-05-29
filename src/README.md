# Prototipo técnico (`src/`)

Contexto del estudio PF-3311, diseño experimental y documentación: ver [README principal](../README.md).

## Layout

| Path | Role |
|------|------|
| [`familiar_godot/`](familiar_godot/) | Godot 4.6 client — naivee VRM avatar, WebSocket, audio |
| [`backend/`](backend/) | Python FastAPI service — Ollama chat stream, Edge-TTS |

## Run the buddy (dev)

1. **Ollama** — install and run locally, then pull a model (example):

   `ollama pull llama3.2`

2. **Backend** — from `src/backend/` ([uv](https://docs.astral.sh/uv/)):

   ```bash
   uv sync
   copy .env.example .env
   uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --reload-exclude "data/*" --reload-exclude "*.db"
   ```

   Research dashboard:

   - `http://127.0.0.1:8000/research/dashboard`

3. **Godot** — open `src/familiar_godot/project.godot`, run the main scene (naivee VRM avatar; first open imports assets). Default WebSocket: `ws://127.0.0.1:8000/ws/session`. Override via **Backend Ws** or env `FAMILIAR_BACKEND_WS`.

Configure the LLM in `src/backend/.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`; see `.env.example`). Local Ollama needs no API key.

Requires network for **Edge-TTS**. Whisper / mic endpointing are wired as libraries and modules for the next milestone; the current loop is **typed text → Ollama → optional animation JSON → MP3**.

## Docker shortcut

From repo root:

```bash
docker compose up --build -d
docker exec -it pf3311-ollama ollama pull llama3.1:latest
```

Shipping notes (Godot binary + Docker backend + LLM env): [`docs/DEPLOY.md`](../docs/DEPLOY.md).
