from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import make_token, require_admin
from app.database import get_session
from app.models import Match, Player, Team
from app.presenters import build_match_state, public_player, public_team, short_match
from app.schemas import (
    AdminLoginIn,
    BountyIn,
    PinIn,
    PlayerStatusIn,
    RecalcIn,
    RoundIn,
    ScoreIn,
    StatusIn,
    TreasuryIn,
)
from app.services import (
    add_treasury,
    delete_event,
    force_status,
    get_match,
    league_snapshot,
    recalculate,
    set_bounty,
    set_pin,
    set_player_status,
    set_round,
    set_score,
)
from app.auth import check_master_key

router = APIRouter(prefix="/admin")


@router.post("/login")
def admin_login(payload: AdminLoginIn) -> dict:
    check_master_key(payload.master_key)
    return {"token": make_token("admin")}


@router.get("/overview")
def overview(_: str = Depends(require_admin), session: Session = Depends(get_session)) -> dict:
    teams = list(session.exec(select(Team).order_by(Team.name)).all())
    players = list(session.exec(select(Player).order_by(Player.team_id, Player.number)).all())
    matches = list(session.exec(select(Match).order_by(Match.round_number, Match.id)).all())
    return {
        "league": league_snapshot(session),
        "teams": [public_team(team, include_pin=True) for team in teams],
        "players": [public_player(player) for player in players],
        "matches": [short_match(session, match) for match in matches],
    }


@router.get("/matches/{match_id}")
def admin_match(
    match_id: int,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return build_match_state(session, get_match(session, match_id))


@router.post("/matches/{match_id}/status")
def admin_status(
    match_id: int,
    payload: StatusIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return force_status(session, get_match(session, match_id), payload.status)


@router.patch("/matches/{match_id}/score")
def admin_score(
    match_id: int,
    payload: ScoreIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return set_score(session, get_match(session, match_id), payload.home_td, payload.away_td)


@router.delete("/events/{event_id}")
def admin_delete_event(
    event_id: int,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return delete_event(session, event_id)


@router.post("/teams/{team_id}/treasury")
def admin_treasury(
    team_id: int,
    payload: TreasuryIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    team = session.get(Team, team_id)
    if team is None:
        from app.auth import RuleError

        raise RuleError("Equipo no encontrado.", 404)
    return add_treasury(session, team, payload.delta)


@router.post("/teams/{team_id}/pin")
def admin_pin(
    team_id: int,
    payload: PinIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    team = session.get(Team, team_id)
    if team is None:
        from app.auth import RuleError

        raise RuleError("Equipo no encontrado.", 404)
    return set_pin(session, team, payload.pin)


@router.post("/players/{player_id}/status")
def admin_player_status(
    player_id: int,
    payload: PlayerStatusIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    player = session.get(Player, player_id)
    if player is None:
        from app.auth import RuleError

        raise RuleError("Jugador no encontrado.", 404)
    return set_player_status(session, player, payload.status)


@router.post("/recalculate")
def admin_recalculate(
    payload: RecalcIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return recalculate(session, payload.choices, payload.override)


@router.post("/bounty")
def admin_bounty(
    payload: BountyIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return set_bounty(session, payload.bounty_id)


@router.post("/round")
def admin_round(
    payload: RoundIn,
    _: str = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    return set_round(session, payload.round_number)
