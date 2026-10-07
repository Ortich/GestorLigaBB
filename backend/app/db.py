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
    _ensure_player_spp_columns()
    _ensure_match_event_columns()


def _ensure_columns(table: str, columns: dict[str, str]) -> None:
    """Anade columnas nuevas a una tabla SQLite ya existente."""
    if not _settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        present = {
            row[1]
            for row in connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        }
        if not present:
            return
        for name, declaration in columns.items():
            if name not in present:
                connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _ensure_match_economy_columns() -> None:
    """Anade las columnas del cierre economico si la base ya existia."""
    _ensure_columns(
        "match",
        {
            "home_fans_roll": "INTEGER",
            "away_fans_roll": "INTEGER",
            "home_fans_before": "INTEGER",
            "away_fans_before": "INTEGER",
            "home_fans_after": "INTEGER",
            "away_fans_after": "INTEGER",
            "home_gold_discarded": "INTEGER NOT NULL DEFAULT 0",
            "away_gold_discarded": "INTEGER NOT NULL DEFAULT 0",
            "conceded_by_team_id": "INTEGER",
        },
    )


def _ensure_player_spp_columns() -> None:
    """Anade spp_earned / spp_spent y rellena con el spp disponible actual."""
    _ensure_columns(
        "player",
        {
            "spp_earned": "INTEGER NOT NULL DEFAULT 0",
            "spp_spent": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    if not _settings.database_url.startswith("sqlite"):
        return
    with engine.begin() as connection:
        present = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(player)").fetchall()
        }
        if not present or "spp_earned" not in present:
            return
        # Bases antiguas: el campo spp era el disponible. Lo tomamos como ganado
        # historico (no sabemos cuanto se gasto antes).
        connection.exec_driver_sql(
            "UPDATE player SET spp_earned = spp WHERE spp_earned = 0 AND spp > 0 AND spp_spent = 0"
        )


def _ensure_match_event_columns() -> None:
    _ensure_columns(
        "matchevent",
        {"is_block_casualty": "INTEGER NOT NULL DEFAULT 0"},
    )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
