from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

_TMP_DIR = Path(tempfile.mkdtemp(prefix="bb-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR / 'test.db'}"
os.environ["MASTER_KEY"] = "test-master-key"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FRONTEND_DIST"] = str(_TMP_DIR / "no-frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app import security  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LeagueState, Match, Player, Sponsor, Team  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def session():
    with Session(engine) as db:
        yield db


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- #
# Factorias
# --------------------------------------------------------------------------- #
def make_team(
    session: Session,
    name: str,
    *,
    pin: str = "1234",
    rerolls: int = 0,
    reroll_cost: int = 50_000,
    assistant_coaches: int = 0,
    cheerleaders: int = 0,
    apothecary: bool = False,
    treasury: int = 100_000,
    fans: int = 5,
    race: str = "Humano",
) -> Team:
    team = Team(
        name=name,
        coach_name=f"Coach {name}",
        race=race,
        pin_hash=security.hash_pin(pin),
        treasury=treasury,
        rerolls=rerolls,
        reroll_cost=reroll_cost,
        assistant_coaches=assistant_coaches,
        cheerleaders=cheerleaders,
        apothecary=apothecary,
        fans=fans,
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def add_players(session: Session, team: Team, count: int, value: int = 50_000, **overrides) -> list[Player]:
    players = []
    for index in range(count):
        player = Player(
            team_id=team.id,
            number=index + 1,
            name=f"{team.name} {index + 1}",
            position="Liniero",
            cost=value,
            current_value=value,
            **overrides,
        )
        session.add(player)
        players.append(player)
    session.commit()
    for player in players:
        session.refresh(player)
    return players


def make_match(session: Session, home: Team, away: Team, round_number: int = 1, **overrides) -> Match:
    match = Match(
        round_number=round_number,
        home_team_id=home.id,
        away_team_id=away.id,
        **overrides,
    )
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def seed_sponsors(session: Session) -> list[Sponsor]:
    from seed import seed_sponsors as _seed

    _seed(session)
    return list(session.exec(__import__("sqlmodel").select(Sponsor)).all())


def ensure_state(session: Session, **kwargs) -> LeagueState:
    state = session.get(LeagueState, 1) or LeagueState(id=1)
    for key, value in kwargs.items():
        setattr(state, key, value)
    session.add(state)
    session.commit()
    session.refresh(state)
    return state
