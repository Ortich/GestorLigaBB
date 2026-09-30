#!/usr/bin/env bash
# Genera el export estatico del frontend y arranca FastAPI sirviendolo todo
# desde un unico puerto (el modo recomendado para la noche de liga).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Compilando el frontend"
cd frontend
npm run build
cd ..

echo
echo "==> Sirviendo la app completa en http://0.0.0.0:8000"
cd backend
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
