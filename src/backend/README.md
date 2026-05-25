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
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Environment

See [.env.example](.env.example).

## Dependencies

Edit `pyproject.toml`, then refresh the lockfile:

```bash
uv lock
uv sync
```
