# Dev server (no file-watch reload — SQLite + WebSocket sessions stay stable).
Set-Location $PSScriptRoot\..

Write-Host "Starting backend..." -ForegroundColor Cyan
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
