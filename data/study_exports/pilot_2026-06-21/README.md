# Pilot export — 2026-06-21

Snapshot exported `2026-06-22T00:14:03Z` from Mac local backend + Godot client logs.

**For LLMs:** read [`../LLM.md`](../LLM.md) first — join keys, condition A/B semantics, and which Parquet file to use.

## Quick stats

| Table | Rows |
|-------|------|
| Complete paired runs | 3 (`paired_scores.parquet`) |
| Participants (all) | 5 |
| Dialogue turns | 68 |
| Post-interaction questionnaires | 7 |
| Exit interviews | 5 |

## Primary analysis path

1. `parquet/paired_scores.parquet` — within-subject A vs B composites
2. `parquet/exit_interviews.parquet` — qualitative debrief
3. `parquet/turns.parquet` — transcript + retrieval metadata

See `manifest.json` for full file list and `completeness_report.txt` for missing data flags.
