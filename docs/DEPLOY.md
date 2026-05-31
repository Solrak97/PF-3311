# Shipping layout

| Piece | How you ship it |
|-------|-----------------|
| **Backend** | Docker image (`src/backend/Dockerfile`) — API, WebSocket, TTS, SQLite logging |
| **LLM** | Local Ollama (default) or any OpenAI-compatible HTTP API via env |
| **Godot client** | Exported desktop binary (Windows `.exe`); not in Docker |

## Backend (Docker)

**Stack with bundled Ollama** (lab machine, offline-friendly):

```bash
docker compose up --build -d
docker exec -it pf3311-ollama ollama pull llama3.1:latest
```

**Backend only** (LLM on host or cloud):

```bash
copy .env.docker.example .env
# Edit LLM_BASE_URL, LLM_API_KEY, LLM_MODEL as needed
docker compose -f docker-compose.external-llm.yml up --build -d
```

### LLM environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_PROVIDER` | `ollama` | `ollama` (native `/api/chat`) or `openai_compat` (`/v1/chat/completions`) |
| `LLM_BASE_URL` | from `OLLAMA_BASE_URL` | API root, e.g. `http://127.0.0.1:11434` or `https://api.openai.com` |
| `LLM_MODEL` | from `OLLAMA_MODEL` | Model id |
| `LLM_API_KEY` | empty | Bearer token for remote APIs (unused for local Ollama) |

Local dev without Docker: copy `src/backend/.env.example` → `.env` and run `uv run uvicorn …` as in `src/README.md`.

Health check: `GET http://127.0.0.1:8000/healthz` returns `llm_provider` and `llm_model`.

## Godot client (binary)

1. Open `src/familiar_godot/project.godot` in Godot 4.6.
2. **Project → Export** → add **Windows Desktop** (or target OS).
3. Export to e.g. `dist/PF3311-Client.exe`.

Point the client at the backend:

- **Inspector**: on the chat scene root, set **Backend Ws** (e.g. `ws://192.168.1.10:8000/ws/session`).
- **Environment** (recommended for lab PCs): set before launch:

  ```powershell
  $env:FAMILIAR_BACKEND_WS = "ws://127.0.0.1:8000/ws/session"
  .\PF3311-Client.exe
  ```

The env var overrides the exported default when non-empty.

## Typical lab setup

1. One machine runs `docker compose up` (backend + Ollama).
2. Each participant PC runs the Godot export with `FAMILIAR_BACKEND_WS=ws://<server-ip>:8000/ws/session`.
3. Researcher opens `http://<server-ip>:8000/research/dashboard` for turn logs.
