# Compiled paper PDF (`paper.pdf`)

This file was **not previously in git** because `docs/paper.pdf` was listed in `.gitignore` as a LaTeX build artifact. The PDF was produced locally and shared out-of-band (e.g. Discord) before a successful commit.

## Verification

| Check | Value |
|-------|--------|
| **Source** | `docs/paper.tex` |
| **Matching revision** | `2355d57` — *Revise pilot paper for exploratory mixed-methods results presentation* (2026-06-21) |
| **PDF created (XMP)** | `2026-06-21T22:11:51-06:00` |
| **Toolchain** | LaTeX + acmart 2026/05/31 v2.18 |
| **Title** | Suena Familiar: Percepción de Familiaridad en Agentes Virtuales Mediante Familiaridad Conductual |

Recompile to verify (requires TeX Live / MacTeX):

```bash
cd docs
TEXINPUTS="./paper template//:" latexmk -pdf paper.tex
# diff metadata or visual check against committed paper.pdf
```

Figures and prose in the PDF correspond to `docs/figures/pilot/` and the current `paper.tex` on `main`.
