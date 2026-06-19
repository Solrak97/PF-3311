#!/usr/bin/env bash
# Source on the Mac before running Godot:
#   source scripts/mac-client-env.sh 100.121.211.116
#   source scripts/mac-client-env.sh ganimede-1.tailxxxxx.ts.net
# Or:  export PF3311_SERVER=100.x.x.x && source scripts/mac-client-env.sh

set -euo pipefail

SERVER="${1:-${PF3311_SERVER:-}}"
PORT="${PF3311_PORT:-8000}"

if [[ -z "$SERVER" ]]; then
  echo "Usage: source scripts/mac-client-env.sh <windows-pc-tailscale-ip-or-magicdns>"
  echo "   or: PF3311_SERVER=100.x.x.x source scripts/mac-client-env.sh"
  echo ""
  echo "On the Windows server PC, run: .\\scripts\\experiment-server.ps1 -Action Status"
  echo "to print the Tailscale address to use."
  return 1 2>/dev/null || exit 1
fi

export FAMILIAR_BACKEND_HTTP="http://${SERVER}:${PORT}"
export FAMILIAR_BACKEND_WS="ws://${SERVER}:${PORT}/ws/session"

echo "FAMILIAR_BACKEND_HTTP=$FAMILIAR_BACKEND_HTTP"
echo "FAMILIAR_BACKEND_WS=$FAMILIAR_BACKEND_WS"
echo ""
echo "Test: curl -s \"$FAMILIAR_BACKEND_HTTP/healthz\""
