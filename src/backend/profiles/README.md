# Behavioral profiles (schema + docs)

Committed JSON schemas live in `schema/`. The control baseline for Condition B is committed as `generic_control_agent.yaml`. Runtime trained profile data is written under `data/profiles/` (gitignored).

| Path | Contents |
|------|----------|
| `generic_control_agent.yaml` | Fixed control baseline for Condition B (neutral, non-distinctive) |
| `schema/` | JSON schemas for raw / behavioral trained profiles |
| `data/profiles/raw/` | Training sessions from Train Profile mode |
| `data/profiles/behavioral/` | Compiled profiles used in Condition A |
| `data/profiles/validation/` | Pilot validator ratings |

**Condition A** loads a trained behavioral profile (`Profile A`) with optional contextual retrieval.  
**Condition B** always loads `generic_control_agent.yaml` — no familiarity prompting, no profile-specific retrieval.

See `app/profiles/store.py`, `app/profiles/control.py`, and `app/experiment/chat.py`.
