from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app import league_engine, rules, serializers
from app.deps import SessionDep
from app.models import Bounty, Sponsor
from app.schemas import BountyPublic, LeagueStatePublic, SponsorPublic, StandingRow

router = APIRouter(prefix="/api/league", tags=["liga"])


@router.get("/state", response_model=LeagueStatePublic)
def league_state(session: SessionDep) -> LeagueStatePublic:
    state = league_engine.get_league_state(session)
    return serializers.league_state_public(session, state)


@router.get("/standings", response_model=list[StandingRow])
def standings(session: SessionDep) -> list[StandingRow]:
    return league_engine.compute_standings(session)


@router.get("/sponsors", response_model=list[SponsorPublic])
def sponsors(session: SessionDep) -> list[SponsorPublic]:
    items = session.exec(select(Sponsor).order_by(Sponsor.priority)).all()
    return [serializers.sponsor_public(s) for s in items]


@router.get("/sponsors/preview")
def sponsors_preview(session: SessionDep) -> dict[str, Any]:
    """Como quedarian los patrocinadores con los datos actuales (sin aplicar)."""
    assignments = league_engine.assign_sponsors(session, apply=False, force=True)
    return {
        "evaluated_round": league_engine.last_fully_completed_round(session),
        "first_round": int(rules.sponsor_rules().get("first_round", 3)),
        "assignments": [a.model_dump() for a in assignments],
    }


@router.get("/bounties", response_model=list[BountyPublic])
def bounties(session: SessionDep) -> list[BountyPublic]:
    items = session.exec(select(Bounty).order_by(Bounty.id)).all()
    return [serializers.bounty_public(b) for b in items]
