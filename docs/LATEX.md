# Local LaTeX (Overleaf-style in Cursor)

You can edit, compile, and preview `docs/*.tex` on your machine. This repo is set up for **pdfLaTeX + BibTeX** (same stack as most Overleaf projects).

## 1. Install a TeX distribution (once)

| Option | Install (Windows) | Notes |
|--------|-------------------|--------|
| **MiKTeX** (recommended) | `winget install MiKTeX.MiKTeX` | On-demand packages; lighter start |
| **TeX Live** | `winget install TeXLive.TeXLive2024` | Full install; very large (~5 GB) |

After install, **restart Cursor** so `pdflatex` / `latexmk` are on PATH.

Verify (restart the terminal after install):

```powershell
pdflatex --version
```

If `pdflatex` is not found, add MiKTeX to PATH or use a **new** terminal — default install path:

`%LOCALAPPDATA%\Programs\MiKTeX\miktex\bin\x64`

## 2. Compile from the terminal

```powershell
cd docs
.\compile.ps1 avance_2
```

Other files: `proposal`, `protocolo_evaluacion`.

The script runs **pdflatex → bibtex → pdflatex ×2** (no Perl/`latexmk` required on Windows).

## 3. Overleaf-like edit + preview in Cursor

Install the extension **LaTeX Workshop** (`James-Yu.latex-workshop`).

Open the repo root (or `docs/`). Workspace settings in [`.vscode/settings.json`](../.vscode/settings.json) configure:

- **Build on save** (recipe: pdflatex + bibtex)
- **PDF preview** in a side tab (internal viewer)
- **SyncTeX** — click in PDF to jump to source (like Overleaf)

### Main commands (Command Palette)

| Command | Action |
|---------|--------|
| `LaTeX Workshop: Build LaTeX project` | Compile |
| `LaTeX Workshop: View LaTeX PDF` | Open preview |
| `LaTeX Workshop: View LaTeX PDF file in web browser` | External viewer |

Set the **root file** when editing: open `avance_2.tex`, then *LaTeX Workshop: Set root file* if build picks the wrong `.tex`.

## 4. Bibliography

`avance_2.tex` uses:

```latex
\bibliographystyle{IEEEtran}
\bibliography{references}
```

`references.bib` must stay in `docs/` (same folder as the `.tex` file). First build may need **two runs**; `compile.ps1` (or LaTeX Workshop) runs BibTeX between pdfLaTeX passes automatically.

## 5. Git hygiene

Build artifacts (`*.aux`, `*.log`, `*.pdf`, etc.) under `docs/` are gitignored. Commit only `.tex` / `.bib` sources unless you intentionally want PDFs in the repo.

## 6. vs Overleaf

| Overleaf | This setup |
|----------|------------|
| Cloud compile | Local `pdflatex` + `bibtex` |
| Shared project | Git repo |
| Collaborators | Git + PRs |
| Online PDF viewer | LaTeX Workshop tab or SumatraPDF (optional) |

For exact Overleaf fonts/packages, install missing packages when MiKTeX prompts, or use TeX Live for a full tree.
