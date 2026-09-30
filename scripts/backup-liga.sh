#!/usr/bin/env bash
# Copia consistente de backend/liga.db mientras la app sigue en marcha.
# Guarda las 14 mas recientes en backend/backups/.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="$ROOT/backend/liga.db"
DEST="$ROOT/backend/backups"
STAMP="$(date +%F)"

if [ ! -s "$DB" ]; then
  echo "No hay base de datos en $DB" >&2
  exit 1
fi

mkdir -p "$DEST"
TARGET="$DEST/liga-$STAMP.db"
PY="$ROOT/backend/.venv/bin/python"

if [ -x "$PY" ]; then
  "$PY" - "$DB" "$TARGET" <<'PY'
import sqlite3
import sys

source, target = sys.argv[1], sys.argv[2]
src = sqlite3.connect(source)
dst = sqlite3.connect(target)
with dst:
    src.backup(dst)
dst.close()
src.close()
PY
else
  cp -a "$DB" "$TARGET"
fi

# Deja solo las 14 copias mas nuevas.
mapfile -t OLD < <(ls -1t "$DEST"/liga-*.db 2>/dev/null | tail -n +15 || true)
if [ "${#OLD[@]}" -gt 0 ]; then
  rm -f "${OLD[@]}"
fi

echo "Copia guardada en $TARGET"
