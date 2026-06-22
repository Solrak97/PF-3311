#!/usr/bin/env bash
# Export pilot study data (SQLite + Godot exit interviews) to CSV + Parquet.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXPORT_NAME="${1:-pilot_$(date +%Y-%m-%d)}"
OUT_DIR="$ROOT/data/study_exports/$EXPORT_NAME"
DB="$ROOT/src/backend/data/experiment.db"
GODOT_LOGS="${GODOT_LOGS:-$HOME/Library/Application Support/Godot/app_userdata/PF-3311/experiment_logs/run}"

PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" && -x "$ROOT/src/backend/.venv/bin/python" ]]; then
  PYTHON="$ROOT/src/backend/.venv/bin/python"
elif [[ -z "$PYTHON" ]]; then
  PYTHON="python3"
fi

"$PYTHON" -m pip install -q pandas pyarrow 2>/dev/null \
  || uv pip install --python "$PYTHON" pandas pyarrow 2>/dev/null \
  || true

echo "Export → $OUT_DIR"
echo "  DB:     $DB"
echo "  Godot:  $GODOT_LOGS"

"$PYTHON" "$ROOT/src/analysis/export_study_data.py" \
  --db "$DB" \
  --out "$OUT_DIR" \
  --godot-logs "$GODOT_LOGS"

echo ""
echo "Parquet files:"
ls -lh "$OUT_DIR/parquet/" 2>/dev/null || echo "(none — install pyarrow)"
