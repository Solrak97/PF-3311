# Compile LaTeX in docs/ (pdflatex + bibtex).
# Usage: .\compile.ps1 [avance_2|proposal|protocolo_evaluacion]
param(
    [string]$Name = "avance_2"
)

$ErrorActionPreference = "Stop"
$docs = $PSScriptRoot
$tex = Join-Path $docs "$Name.tex"

if (-not (Test-Path $tex)) {
    Write-Error "Not found: $tex"
}

function Find-LatexTool([string]$tool) {
    $cmd = Get-Command $tool -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        "$env:ProgramFiles\MiKTeX\miktex\bin\x64\$tool.exe",
        "$env:LocalAppData\Programs\MiKTeX\miktex\bin\x64\$tool.exe",
        "C:\texlive\2024\bin\windows\$tool.exe",
        "C:\texlive\2023\bin\windows\$tool.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

$pdflatex = Find-LatexTool "pdflatex"
$bibtex = Find-LatexTool "bibtex"
if (-not $pdflatex) {
    Write-Host @"
LaTeX is not installed or not on PATH.

  winget install MiKTeX.MiKTeX

Restart the terminal, then run this script again.
See docs/LATEX.md for Cursor preview (LaTeX Workshop).
"@ -ForegroundColor Yellow
    exit 1
}

function Invoke-PdfLatex {
    param([string]$PassLabel)
    Write-Host "pdflatex ($PassLabel)..." -ForegroundColor Cyan
    & $pdflatex -interaction=nonstopmode -file-line-error -synctex=1 $Name.tex
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Push-Location $docs
try {
    Invoke-PdfLatex "pass 1"
    if ($bibtex -and (Test-Path "$Name.aux")) {
        Write-Host "bibtex..." -ForegroundColor Cyan
        & $bibtex $Name
        # BibTeX warnings are common; continue if .bbl was produced
    }
    Invoke-PdfLatex "pass 2"
    Invoke-PdfLatex "pass 3"
    $pdf = Join-Path $docs "$Name.pdf"
    if (Test-Path $pdf) {
        Write-Host "OK: $pdf" -ForegroundColor Green
    } else {
        Write-Error "PDF was not created."
    }
} finally {
    Pop-Location
}
