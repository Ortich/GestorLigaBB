#!/usr/bin/env bash
# Arranca backend (FastAPI con recarga) y frontend (Next dev) a la vez.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d backend/.venv ]; then
  echo "Falta el entorno virtual. Ejecuta primero scripts/setup.sh"
  exit 1
fi

cleanup() {
  kill 0 2>/dev/null || true
}
trap cleanup EXIT INT TERM

(
  cd backend
  .venv/bin/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &

(
  cd frontend
  npm run dev
) &

echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
wait
