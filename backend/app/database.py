from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = BACKEND_ROOT / "data" / "league.db"


def database_url() -> str:
    return os.environ.get("BB_DATABASE", f"sqlite:///{DEFAULT_DB}")


def _ensure_parent(url: str) -> None:
    prefix = "sqlite:///"
    if url.startswith(prefix) and url != "sqlite://":
        path = Path(url[len(prefix) :])
        if path.parent and str(path.parent) not in ("", "."):
            path.parent.mkdir(parents=True, exist_ok=True)


_url = database_url()
_ensure_parent(_url)
engine = create_engine(_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
