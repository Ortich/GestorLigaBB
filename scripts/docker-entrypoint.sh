#!/bin/sh
# Arranca la app. Si el volumen de datos esta vacio, crea la liga de ejemplo.
set -eu

mkdir -p /data

DB_FILE="${DB_FILE:-/data/liga.db}"
export DATABASE_URL="${DATABASE_URL:-sqlite:////data/liga.db}"
export FRONTEND_DIST="${FRONTEND_DIST:-/app/frontend/out}"

if [ ! -s "$DB_FILE" ]; then
  echo "No hay liga en $DB_FILE. Creando los 8 equipos de ejemplo."
  cd /app/backend
  python seed.py
fi

cd /app/backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
