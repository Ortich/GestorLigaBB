from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_settings = get_settings()

connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(_settings.database_url, echo=False, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - infra
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        pass


def init_db() -> None:
    # Importa los modelos para que SQLModel registre las tablas.
    from app import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_match_economy_columns()


def _ensure_match_economy_columns() -> None:
    """Anade las columnas del cierre economico si la base ya existia."""
    if not _settings.database_url.startswith("sqlite"):
        return
    columns = {
        "home_fans_roll": "INTEGER",
        "away_fans_roll": "INTEGER",
        "home_fans_before": "INTEGER",
        "away_fans_before": "INTEGER",
        "home_fans_after": "INTEGER",
        "away_fans_after": "INTEGER",
        "home_gold_discarded": "INTEGER NOT NULL DEFAULT 0",
        "away_gold_discarded": "INTEGER NOT NULL DEFAULT 0",
        "conceded_by_team_id": "INTEGER",
    }
    with engine.begin() as connection:
        present = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(match)").fetchall()
        }
        if not present:
            return
        for name, declaration in columns.items():
            if name not in present:
                connection.exec_driver_sql(f"ALTER TABLE match ADD COLUMN {name} {declaration}")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
