#!/usr/bin/env bash
# Instala dependencias y crea la liga con los 8 equipos de ejemplo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Backend"
cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv 2>/dev/null || uv venv .venv
fi
if [ -x .venv/bin/pip ]; then
  .venv/bin/pip install -q -r requirements.txt
else
  uv pip install --python .venv/bin/python -r requirements.txt
fi
.venv/bin/python seed.py
cd ..

echo "==> Frontend"
cd frontend
npm install
cd ..

echo
echo "Listo. Arranca la app en modo desarrollo con: scripts/dev.sh"
echo "O genera el build de produccion con:          scripts/build.sh"
