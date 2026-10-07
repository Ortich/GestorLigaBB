# Arranca la liga en local, sin Docker (Windows).
# Un solo proceso de Python. Ctrl+C para pararla.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path "backend\.venv\Scripts\python.exe")) {
    Write-Error "Falta el entorno de Python. Ejecuta primero: .\scripts\setup.ps1"
}

if (-not (Test-Path "frontend\out\index.html")) {
    Write-Host "==> Compilando la interfaz (solo hace falta la primera vez, o si cambias el frontend)"
    Push-Location frontend
    npm run build
    Pop-Location
}

$db = Get-Item "backend\liga.db" -ErrorAction SilentlyContinue
if (-not $db -or $db.Length -eq 0) {
    Write-Host "==> No hay liga todavia. Creando los 8 equipos de ejemplo."
    Push-Location backend
    & .\.venv\Scripts\python.exe seed.py
    Pop-Location
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host ""
Write-Host "Liga lista."
Write-Host "  En este PC:     http://localhost:8000"
if ($ip) {
    Write-Host "  En los moviles: http://${ip}:8000   (misma WiFi)"
}
Write-Host "  Base de datos:  backend\liga.db"
Write-Host ""
Write-Host "Cierrala con Ctrl+C. No queda ningun servicio en segundo plano."
Write-Host ""

Set-Location "$Root\backend"
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
