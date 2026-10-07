# Arranca backend (FastAPI con recarga) y frontend (Next dev) a la vez (Windows).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:PYTHONIOENCODING = "utf-8"

if (-not (Test-Path "backend\.venv\Scripts\python.exe")) {
    Write-Error "Falta el entorno virtual. Ejecuta primero .\scripts\setup.ps1"
}

$backend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$Root\backend" `
    -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"

$frontend = Start-Process -PassThru -NoNewWindow -WorkingDirectory "$Root\frontend" `
    -FilePath "npm" `
    -ArgumentList "run", "dev"

Write-Host "Backend:  http://localhost:8000/docs"
Write-Host "Frontend: http://localhost:3000"
Write-Host "Ctrl+C para parar ambos."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    foreach ($proc in @($backend, $frontend)) {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
