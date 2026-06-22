# Study data exports — LLM ingestion guide

**Purpose:** Within-subjects pilot for *Suena Familiar* (PF-3311). Each participant chats with two agents (Condition **A** = trained behavioral profile, Condition **B** = generic control), fills Likert questionnaires after each interaction, then optional open-ended exit interview.

**Start here:** `pilot_2026-06-21/manifest.json` (row counts, export time) and `pilot_2026-06-21/completeness_report.txt`.

## Recommended files (prefer Parquet)

```
data/study_exports/pilot_2026-06-21/parquet/
  paired_scores.parquet      ← primary analysis table (3 complete runs, A vs B)
  questionnaires_wide.parquet ← 7 post-interaction surveys (38 items + composites)
  turns.parquet              ← 68 dialogue turns with metadata
  exit_interviews.parquet    ← 5 open-ended debriefs (NOT in SQLite; from Godot)
  runs_summary.parquet       ← run-level completeness flags
  sessions.parquet           ← 8 interaction blocks
  questionnaires_long.parquet← item-level long format
```

CSV mirrors live alongside Parquet in the same folder. `turns.jsonl` has full nested `turn_metadata`.

## Join keys

| Key | Use |
|-----|-----|
| `participant_id` | e.g. `pf002`, `pf004`, `pf005` |
| `run_session_id` | Experiment run id without `-i1`/`-i2` suffix (e.g. `exp-70d0b68738d7b9b3`) |
| `session_id` | One interaction block: `{run_session_id}-i1` or `-i2` |
| `condition` | `A` (trained profile) or `B` (control) |
| `order_group` | Counterbalance: `A-B` or `B-A` |
| `interaction_index` | `1` or `2` (order within run) |
| `profile_id` | `pf-0001` on A; `generic_control_agent` on B |

**Join exit interviews → runs:** `exit_interviews.run_session_id` = `runs_summary.run_session_id` = prefix of `sessions.session_id`.

**Join turns → questionnaires:** same `session_id`, or match `participant_id` + `condition` + `interaction_index`.

## Condition semantics (critical)

- **Condition A:** Trained profile `pf-0001` — familiarity prompting, retrieval, behavioral plan active.
- **Condition B:** Fixed control `generic_control_agent` — neutral, no profile-specific retrieval.
- **Order matters:** `order_group=A-B` → interaction 1 is A; `B-A` → interaction 1 is B.

## Complete runs (use for paired analysis)

Filter `runs_summary.parquet` where `run_complete == true` (or use `paired_scores.parquet` directly):

| participant_id | run_session_id | order_group |
|----------------|----------------|-------------|
| pf002 | exp-70d0b68738d7b9b3 | A-B |
| pf004 | exp-e73ee18b6c259505 | B-A |
| pf005 | exp-bab25091ac7cd8dc | A-B |

Incomplete: `test` (partial), `pf003` (aborted, 0 turns).

## Questionnaire constructs (`questionnaires_wide`)

Columns prefixed `item__` are raw Likert/SAM/Godspeed items. Composite columns (means):

| Composite | Construct |
|-----------|-----------|
| `closeness` | Perceived closeness (RQ) |
| `familiarity` | Behavioral familiarity |
| `context_knowledge` | “Knew me” / dependability |
| `sam_valence`, `sam_arousal`, `sam_dominance` | SAM affect |
| `godspeed_*` | Anthropomorphism, animacy, likeability, intelligence, safety |

Scales: Likert 1–7, Godspeed 1–5, SAM 1–9.

## Turn metadata (`turns.turn_metadata_json`)

JSON string per turn. Typical keys:

- `active_situation` — detected conversational mode (A only)
- `retrieval_used` — bool, profile moment retrieval (A only)
- `moment_ids` — retrieved example ids
- `has_behavioral_plan` — bool

## Exit interview (`exit_interviews`)

Five open-ended questions per run: columns `q1_question`, `q1_answer`, … `q5_answer`. Spanish free text. Only collected locally in Godot; merged at export time.

## Load examples

```python
import pandas as pd
from pathlib import Path

root = Path("data/study_exports/pilot_2026-06-21/parquet")
paired = pd.read_parquet(root / "paired_scores.parquet")
turns = pd.read_parquet(root / "turns.parquet")
exit_qa = pd.read_parquet(root / "exit_interviews.parquet")
```

```python
# DuckDB
import duckdb
duckdb.sql("SELECT * FROM 'data/study_exports/pilot_2026-06-21/parquet/turns.parquet' LIMIT 5")
```

## Regenerate export

```bash
./scripts/export-study-data.sh pilot_2026-06-21
```

Requires local `src/backend/data/experiment.db` and Godot logs at  
`~/Library/Application Support/Godot/app_userdata/PF-3311/experiment_logs/run/` (Mac).

## Analysis entry points in repo

- `src/analysis/run_pilot_analysis.py` — stats + figures from SQLite
- `src/analysis/export_study_data.py` — this export pipeline
- `src/analysis/mappings.py` — item id → construct labels
