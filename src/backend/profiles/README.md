# Behavioral profiles (schema + docs)

Committed JSON schemas live in `schema/`. The control baseline for Condition B is committed as `generic_control_agent.yaml`. Runtime trained profile data is written under `data/profiles/` (gitignored).

| Path | Contents |
|------|----------|
| `generic_control_agent.yaml` | Fixed control baseline for Condition B (neutral, non-distinctive) |
| `baseline_sassy_gf.yaml` | Test baseline for Buddy eval — sarcastic annoying girlfriend (Spanish) |
| `baseline_sassy_gf.raw.json` | Raw samples for retrieval; seed with `scripts/seed_baseline_sassy_gf.py` |
| `schema/` | JSON schemas for raw / behavioral trained profiles |
| `data/profiles/raw/` | Training sessions from Train Profile mode |
| `data/profiles/behavioral/` | Compiled profiles used in Condition A |
| `data/profiles/validation/` | Pilot validator ratings |
| `data/evaluations/` | Local AI-judge / ablation outputs (gitignored; regenerate with `scripts/run_long_chat_judge.py`) |

**Condition A** loads a trained behavioral profile (`Profile A`) with optional contextual retrieval.  
**Condition B** always loads `generic_control_agent.yaml` — no familiarity prompting, no profile-specific retrieval.

See `app/profiles/store.py`, `app/profiles/control.py`, and `app/experiment/chat.py`.
