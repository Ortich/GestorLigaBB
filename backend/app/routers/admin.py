"""Panel del Comisario. Toda la ruta va protegida por la MASTER_KEY."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app import league_engine, match_service, serializers
from app.deps import MasterKey, SessionDep
from app.errors import LeagueError, NotFoundError
from app.models import Bounty, Match, MatchEvent, Player, PlayerStatus, Sponsor, Team
from app.schemas import (
    AdminLeagueStateRequest,
    AdminMatchStatusRequest,
    AdminPlayerRequest,
    AdminScoreRequest,
    AdminSponsorOverrideRequest,
    AdminTreasuryRequest,
    MatchDetail,
    PlayerPublic,
    TeamDetail,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login")
def admin_login(_: MasterKey) -> dict[str, bool]:
    """Valida la MASTER_KEY para que el frontend pueda abrir el panel."""
    return {"ok": True}


@router.get("/overview")
def overview(_: MasterKey, session: SessionDep) -> dict[str, Any]:
    state = league_engine.get_league_state(session)
    matches = session.exec(select(Match).order_by(Match.round_number, Match.id)).all()
    return {
        "league": serializers.league_state_public(session, state).model_dump(),
        "teams": [serializers.team_summary(session, t).model_dump() for t in session.exec(select(Team).order_by(Team.name)).all()],
        "matches": [serializers.match_summary(session, m).model_dump() for m in matches],
        "sponsors": [serializers.sponsor_public(s).model_dump() for s in session.exec(select(Sponsor).order_by(Sponsor.priority)).all()],
        "bounties": [serializers.bounty_public(b).model_dump() for b in session.exec(select(Bounty)).all()],
    }


# --------------------------------------------------------------------------- #
# Gestor de actas
# --------------------------------------------------------------------------- #
@router.post("/matches/{match_id}/status", response_model=MatchDetail)
def force_match_status(
    match_id: int, payload: AdminMatchStatusRequest, _: MasterKey, session: SessionDep
) -> MatchDetail:
    match = match_service.get_match(session, match_id)
    return serializers.match_detail(session, match_service.force_status(session, match, payload.status))


@router.patch("/matches/{match_id}/score", response_model=MatchDetail)
def set_score(
    match_id: int, payload: AdminScoreRequest, _: MasterKey, session: SessionDep
) -> MatchDetail:
    match = match_service.get_match(session, match_id)
    if payload.home_td is not None:
        if payload.home_td < 0:
            raise LeagueError("El marcador no puede ser negativo.")
        match.home_td = payload.home_td
    if payload.away_td is not None:
        if payload.away_td < 0:
            raise LeagueError("El marcador no puede ser negativo.")
        match.away_td = payload.away_td
    session.add(match)
    session.commit()
    session.refresh(match)
    return serializers.match_detail(session, match)


@router.delete("/events/{event_id}")
def delete_event(event_id: int, _: MasterKey, session: SessionDep) -> dict[str, bool]:
    event = session.get(MatchEvent, event_id)
    if event is None:
        raise NotFoundError("Evento no encontrado.")
    match_service.delete_event(session, event_id)
    return {"ok": True}


@router.post("/matches/{match_id}/bounty")
def set_match_bounty(
    match_id: int, bounty_id: int | None, _: MasterKey, session: SessionDep
) -> MatchDetail:
    match = match_service.get_match(session, match_id)
    match.bounty_id = bounty_id
    session.add(match)
    session.commit()
    session.refresh(match)
    return serializers.match_detail(session, match)


# --------------------------------------------------------------------------- #
# Gestor de tesoreria y salud
# --------------------------------------------------------------------------- #
@router.post("/teams/{team_id}/treasury", response_model=TeamDetail)
def adjust_treasury(
    team_id: int, payload: AdminTreasuryRequest, _: MasterKey, session: SessionDep
) -> TeamDetail:
    team = session.get(Team, team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    if team.treasury + payload.delta < 0:
        raise LeagueError("La tesoreria no puede quedar en negativo.")
    team.treasury += payload.delta
    session.add(team)
    session.commit()
    session.refresh(team)
    return serializers.team_detail(session, team)


@router.patch("/players/{player_id}", response_model=PlayerPublic)
def edit_player(
    player_id: int, payload: AdminPlayerRequest, _: MasterKey, session: SessionDep
) -> PlayerPublic:
    player = session.get(Player, player_id)
    if player is None:
        raise NotFoundError("Jugador no encontrado.")
    if payload.status is not None:
        player.status = payload.status
        if payload.status == PlayerStatus.ACTIVE:
            player.mng_match_id = None
    for field in ("spp_earned", "spp_spent", "current_value", "ma", "st", "ag", "pa", "av"):
        value = getattr(payload, field)
        if value is not None:
            setattr(player, field, value)
    if payload.spp is not None:
        # Compat: fijar PE disponibles ajustando lo ganado, sin tocar lo gastado.
        player.spp_earned = max(player.spp_spent, payload.spp + player.spp_spent)
    player.spp = player.spp_available
    session.add(player)
    session.commit()
    session.refresh(player)
    return serializers.player_public(player)


@router.post("/teams/{team_id}/reset-pin")
def reset_pin(team_id: int, pin: str, _: MasterKey, session: SessionDep) -> dict[str, bool]:
    from app import security

    team = session.get(Team, team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    try:
        team.pin_hash = security.hash_pin(pin)
    except ValueError as exc:
        raise LeagueError(str(exc)) from exc
    session.add(team)
    session.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Estado de liga, patrocinadores y recalculo
# --------------------------------------------------------------------------- #
@router.patch("/league")
def update_league(payload: AdminLeagueStateRequest, _: MasterKey, session: SessionDep) -> dict[str, Any]:
    state = league_engine.get_league_state(session)
    if payload.current_round is not None:
        if payload.current_round < 1:
            raise LeagueError("La jornada debe ser 1 o superior.")
        state.current_round = payload.current_round
    if payload.total_rounds is not None:
        state.total_rounds = payload.total_rounds
    if payload.active_bounty_id is not None:
        state.active_bounty_id = payload.active_bounty_id or None
    session.add(state)
    session.commit()
    return serializers.league_state_public(session, state).model_dump()


@router.post("/sponsors/override")
def override_sponsor(
    payload: AdminSponsorOverrideRequest, _: MasterKey, session: SessionDep
) -> dict[str, Any]:
    sponsor = session.exec(select(Sponsor).where(Sponsor.code == payload.sponsor_code)).first()
    if sponsor is None:
        raise NotFoundError("Patrocinador no encontrado.")

    for team in session.exec(select(Team).where(Team.current_sponsor_id == sponsor.id)).all():
        team.current_sponsor_id = None
        session.add(team)

    if payload.team_id is not None:
        team = session.get(Team, payload.team_id)
        if team is None:
            raise NotFoundError("Equipo no encontrado.")
        team.current_sponsor_id = sponsor.id
        session.add(team)

    session.commit()
    return {"ok": True, "sponsor": sponsor.code, "team_id": payload.team_id}


@router.post("/recalculate")
def recalculate(_: MasterKey, session: SessionDep) -> dict[str, Any]:
    """Boton de peligro: regenera marcadores, clasificacion y patrocinadores."""
    return league_engine.recalculate_league(session)
