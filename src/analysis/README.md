# Análisis de datos experimentales

Pipeline de extracción, estadística intra-sujetos y figuras para **Suena Familiar** (PF-3311).

## Pre-vuelo (mañana del estudio)

```powershell
cd src\backend
pip install -e .
pip install -r ..\analysis\requirements.txt
python scripts\preflight_experiment.py
```

Tras cada sesión:

```powershell
python scripts\run_pilot_analysis.py
```


```powershell
cd src\analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m ipykernel install --user --name suena-familiar
```

## Flujo recomendado

### 1. Probar el pipeline con datos sintéticos (antes del estudio real)

```powershell
cd src\analysis
python generate_demo_data.py
python run_pilot_analysis.py --db exports\demo_synthetic\experiment_demo.db --out exports\demo_synthetic
```

Revisa `exports/demo_synthetic/analysis/report.md`.

### 2. Piloto real (bundle en git, solo datos observados)

Cohorte analizable: **n=3** completos (`pf002`, `pf004`, `pf005`).

```powershell
cd src\backend
uv run python ..\analysis\run_pilot_analysis.py --from-export ..\..\data\study_exports\pilot_2026-06-21
```

- Datos: `data/study_exports/pilot_2026-06-21/`
- Estadística: `.../analysis/report.md`
- Insights para el caso: `.../analysis/case_insights.md`

Regenerar export (Mac, SQLite + logs Godot): `./scripts/export-study-data.sh pilot_2026-06-21`

### 3. Después de más sesiones reales

```powershell
cd src\backend
python scripts\run_pilot_analysis.py
```

O desde `src/analysis`:

```powershell
python run_pilot_analysis.py --db ..\backend\data\experiment.db
```

### 3. Notebook interactivo

```powershell
cd src\analysis\notebooks
jupyter notebook pilot_analysis.ipynb
```

En la celda de configuración, deja `USE_DEMO_DB = False` para la base real.

## Salidas

| Ruta | Contenido |
|------|-----------|
| `exports/<run>/` | CSV crudos (sesiones, turnos, cuestionarios, paired_scores) |
| `exports/<run>/analysis/stats_primary.csv` | Pruebas pareadas PI1–PI4 (t, p, dz) |
| `exports/<run>/analysis/stats_exploratory.csv` | Godspeed/SAM adicionales |
| `exports/<run>/analysis/paired_scores.csv` | Una fila por participante, columnas _A/_B/_diff |
| `exports/<run>/analysis/report.md` | Informe legible para el paper |
| `exports/<run>/analysis/figures/*.png` | Figuras listas para `docs/paper.tex` |

## Diseño estadístico

- **Intra-sujetos:** cada participante tiene puntuación en A y en B.
- **Prueba principal:** *t* pareada (dos colas) + **p una cola** para hipótesis A > B del paper.
- **Robustez:** Wilcoxon pareado; Shapiro sobre diferencias (solo informativo).
- **Efecto:** Cohen's *d*z = media(diferencias) / DE(diferencias).
- **Orden:** tabla `order_effects.csv` (interacción 1 vs 2, exploratorio).
- **Ítems:** `stats_items_descriptive.csv` (todas las escalas Likert/Godspeed/SAM).

Con ~5 participantes piloto, interpretar como **exploratorio** (tamaños del efecto + cualitativo).

## Scripts

| Script | Uso |
|--------|-----|
| `export_study_data.py` | Solo extracción CSV |
| `run_pilot_analysis.py` | Extracción + análisis + figuras |
| `generate_demo_data.py` | Base SQLite sintética (5 participantes) |
| `db_extract.py` | API pandas (importable) |
| `stats_pilot.py` | Pruebas y figuras (importable) |

## Fuentes de datos

| Origen | Ubicación |
|--------|-----------|
| SQLite | `src/backend/data/experiment.db` |
| Validación Fase 1 | `src/backend/data/profiles/validation/` |
| Panel | http://127.0.0.1:8000/research/dashboard |

No versionar `experiment.db` ni exports con IDs reales.
