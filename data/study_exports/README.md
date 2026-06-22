# Study exports (committed snapshots)

Version-controlled exports of pilot experiment data for analysis outside the live backend.

## Regenerate

```bash
./scripts/export-study-data.sh pilot_2026-06-21
```

Uses:

- `src/backend/data/experiment.db` — sessions, turns, Likert questionnaires
- `~/Library/Application Support/Godot/app_userdata/PF-3311/experiment_logs/run/` — exit-interview QA (open-ended)

## Layout

| Path | Contents |
|------|----------|
| `parquet/*.parquet` | Analysis-ready tables (pandas / R / DuckDB) |
| `*.csv` | Same data, human-readable |
| `turns.jsonl` | Full dialogue + turn metadata |
| `exit_interviews.csv` | Debrief Q&A (not in SQLite) |
| `manifest.json` | Export timestamp and row counts |

## Parquet tables

- `sessions` — interaction blocks (A/B, duration, end reason)
- `turns` — dialogue + `turn_metadata_json`
- `questionnaires_wide` — one row per post-interaction survey (38 items + composites)
- `questionnaires_long` — item-level long format
- `runs_summary` — one row per participant run
- `paired_scores` — within-subject A vs B (complete runs only)
- `exit_interviews` — open-ended debrief (5 questions)

## Load in Python

```python
import pandas as pd
from pathlib import Path

root = Path("data/study_exports/pilot_2026-06-21/parquet")
turns = pd.read_parquet(root / "turns.parquet")
exit_qa = pd.read_parquet(root / "exit_interviews.parquet")
```
