# Instala dependencias y crea la liga con los 8 equipos de ejemplo (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"

Write-Host "==> Backend"
Set-Location "$Root\backend"

$Py312 = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (-not (Test-Path $Py312)) {
    $Py312 = (py -3.12 -c "import sys; print(sys.executable)" 2>$null)
}
if (-not $Py312 -or -not (Test-Path $Py312)) {
    Write-Error "Falta Python 3.12. Instala Python.Python.3.12 con winget o desde python.org"
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $Py312 -m venv .venv
}

& .\.venv\Scripts\pip.exe install -q -r requirements.txt
& .\.venv\Scripts\python.exe seed.py
Set-Location $Root

Write-Host "==> Frontend"
Set-Location "$Root\frontend"
npm install
Set-Location $Root

Write-Host ""
Write-Host "Listo."
Write-Host "  En tu PC:  .\scripts\start.ps1"
Write-Host "  Dev mode:  .\scripts\dev.ps1"
