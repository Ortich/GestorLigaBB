#!/usr/bin/env python3
"""Sustituye los PIN de ejemplo (1111, 2222, ...) por unos aleatorios.

Pensado para el servidor publico: esos PIN salen en el README y no pueden
quedarse en una liga accesible desde internet. Imprime una linea por equipo.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlmodel import Session, select  # noqa: E402

from app import security  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Team  # noqa: E402


def main() -> None:
    init_db()
    with Session(engine) as session:
        teams = list(session.exec(select(Team).order_by(Team.id)).all())
        if not teams:
            sys.exit("No hay equipos en la base. Ejecuta seed.py antes.")
        rows: list[tuple[str, str, str]] = []
        for team in teams:
            pin = f"{secrets.randbelow(10000):04d}"
            team.pin_hash = security.hash_pin(pin)
            session.add(team)
            rows.append((team.name, team.coach_name, pin))
        session.commit()
    print("Equipo\tEntrenador\tPIN")
    for name, coach, pin in rows:
        print(f"{name}\t{coach}\t{pin}")


if __name__ == "__main__":
    main()
