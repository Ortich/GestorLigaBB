#!/usr/bin/env python3
"""Juega la liga de ejemplo y escribe el acta de la temporada.

No toca backend/liga.db: usa una base temporal.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp(prefix='bb-sim-')}/sim.db"
os.environ["MASTER_KEY"] = "simulacion"
os.environ["SECRET_KEY"] = "simulacion"
os.environ["FRONTEND_DIST"] = str(ROOT / "frontend" / "out")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from simulacion import formatear, simular  # noqa: E402


def main() -> None:
    with TestClient(app) as client:
        print(formatear(simular(client)))


if __name__ == "__main__":
    main()
