from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from sqlmodel import select

from app import league_engine, rules, serializers
from app.deps import SessionDep
from app.models import Bounty, ChronicleEntry, ChronicleKind, Sponsor, TreasurySpill
from app.schemas import (
    BountyPublic,
    ChronicleEntryPublic,
    LeagueStatePublic,
    SponsorPublic,
    StandingRow,
    TreasurySpillPublic,
)

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


@router.get("/spills", response_model=list[TreasurySpillPublic])
def treasury_spills(session: SessionDep, round_number: Optional[int] = None) -> list[TreasurySpillPublic]:
    """Oro perdido en la taberna. Sin jornada devuelve la temporada; con ella, solo esa."""
    query = select(TreasurySpill).order_by(TreasurySpill.round_number, TreasurySpill.id)
    if round_number is not None:
        query = query.where(TreasurySpill.round_number == round_number)
    rows = session.exec(query).all()
    return [serializers.spill_public(session, row) for row in rows]


@router.get("/chronicle", response_model=list[ChronicleEntryPublic])
def chronicle(
    session: SessionDep,
    round_number: Optional[int] = None,
    kind: Optional[ChronicleKind] = None,
) -> list[ChronicleEntryPublic]:
    """Hechos de la temporada, o de una jornada, en el orden del informe."""
    query = select(ChronicleEntry).order_by(
        ChronicleEntry.round_number, ChronicleEntry.sort_order, ChronicleEntry.id
    )
    if round_number is not None:
        query = query.where(ChronicleEntry.round_number == round_number)
    if kind is not None:
        query = query.where(ChronicleEntry.kind == kind)
    return [serializers.chronicle_public(row) for row in session.exec(query).all()]


@router.get("/bounties", response_model=list[BountyPublic])
def bounties(session: SessionDep) -> list[BountyPublic]:
    items = session.exec(select(Bounty).order_by(Bounty.id)).all()
    return [serializers.bounty_public(b) for b in items]
