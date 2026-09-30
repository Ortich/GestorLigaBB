#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACK_PID=$!
cd "$ROOT/frontend"
npm run dev &
FRONT_PID=$!
trap 'kill $BACK_PID $FRONT_PID' EXIT
wait
