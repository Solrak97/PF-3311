# Dev server: reload on code changes, NOT on SQLite experiment logs (avoids WS drops).
Set-Location $PSScriptRoot\..
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 `
  --reload-exclude "data/*" `
  --reload-exclude "*.db" `
  --reload-exclude "*.db-*"
