#!/usr/bin/env bash
# Arranca la liga en local, sin Docker.
# Un solo proceso de Python. Al cerrar esta terminal, la app se para y no queda
# nada residente. La base de datos es el fichero backend/liga.db.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -x backend/.venv/bin/python ]; then
  echo "Falta el entorno de Python. Ejecuta primero: scripts/setup.sh"
  exit 1
fi

if [ ! -f frontend/out/index.html ]; then
  echo "==> Compilando la interfaz (solo hace falta la primera vez, o si cambias el frontend)"
  (cd frontend && npm run build)
fi

if [ ! -s backend/liga.db ]; then
  echo "==> No hay liga todavia. Creando los 8 equipos de ejemplo."
  (cd backend && .venv/bin/python seed.py)
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"

echo
echo "Liga lista."
echo "  En este PC:     http://localhost:8000"
if [ -n "${IP}" ]; then
  echo "  En los moviles: http://${IP}:8000   (misma WiFi)"
fi
echo "  Base de datos:  backend/liga.db"
echo
echo "Cierrala con Ctrl+C. No queda ningun servicio en segundo plano."
echo

cd backend
exec .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
