from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import RuleError, check_pin, get_current_team, make_token
from app.database import get_session
from app.league_engine import calculate_ctv, load_rules
from app.models import Match, Player, Team
from app.presenters import build_match_state, public_player, public_team, short_match
from app.schemas import (
    BenefitIn,
    CompleteIn,
    EventIn,
    InducementsIn,
    LoginIn,
    PlayerUpdateIn,
    ReadyIn,
    RollsIn,
    TurnIn,
)
from app.services import (
    add_event,
    apply_rolls,
    assert_participant,
    begin_match,
    complete_match,
    confirm_ready,
    ensure_state,
    get_match,
    league_snapshot,
    set_inducements,
    set_turn,
    undo_last_event,
    update_player,
    use_benefit,
)

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"ok": True, "name": "Liga Blood Bowl"}


@router.get("/rules")
def rules() -> dict:
    return load_rules()


@router.get("/teams")
def list_teams(session: Session = Depends(get_session)) -> list[dict]:
    teams = session.exec(select(Team).order_by(Team.name)).all()
    return [public_team(team) for team in teams]


@router.post("/auth/login")
def login(payload: LoginIn, session: Session = Depends(get_session)) -> dict:
    team = session.get(Team, payload.team_id)
    if team is None:
        raise RuleError("Equipo no encontrado.", 404)
    check_pin(team, payload.pin)
    return {"token": make_token(f"team:{team.id}"), "team": public_team(team)}


@router.get("/league")
def league(session: Session = Depends(get_session)) -> dict:
    snapshot = league_snapshot(session)
    snapshot["scoring_summary"] = load_rules()["scoring"]["summary"]
    return snapshot


@router.get("/fixtures")
def fixtures(round_number: int | None = None, session: Session = Depends(get_session)) -> list[dict]:
    statement = select(Match).order_by(Match.round_number, Match.id)
    if round_number is not None:
        statement = statement.where(Match.round_number == round_number)
    return [short_match(session, match) for match in session.exec(statement).all()]


@router.get("/dashboard")
def dashboard(team: Team = Depends(get_current_team), session: Session = Depends(get_session)) -> dict:
    players = list(session.exec(select(Player).where(Player.team_id == team.id)).all())
    players.sort(key=lambda player: player.number)
    state = ensure_state(session)
    snapshot = league_snapshot(session)
    upcoming = session.exec(
        select(Match)
        .where(Match.round_number == state.current_round)
        .where((Match.home_team_id == team.id) | (Match.away_team_id == team.id))
    ).first()
    round_rows = session.exec(select(Match).where(Match.round_number == state.current_round)).all()
    return {
        "team": public_team(team),
        "roster": [public_player(player) for player in players],
        "ctv": calculate_ctv(team, players),
        "standings": snapshot["standings"],
        "scoring_summary": load_rules()["scoring"]["summary"],
        "current_round": snapshot["current_round"],
        "active_bounty": snapshot["active_bounty"],
        "sponsor_log": snapshot["sponsor_log"],
        "next_match": short_match(session, upcoming) if upcoming else None,
        "round_matches": [short_match(session, match) for match in round_rows],
    }


@router.patch("/players/{player_id}")
def patch_player(
    player_id: int,
    payload: PlayerUpdateIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    return update_player(session, team, player_id, payload)


def _playable(match_id: int, team: Team, session: Session) -> Match:
    match = get_match(session, match_id)
    assert_participant(match, team)
    return match


@router.get("/matches/{match_id}")
def read_match(
    match_id: int,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    return build_match_state(session, _playable(match_id, team, session))


@router.post("/matches/{match_id}/ready")
def ready(
    match_id: int,
    payload: ReadyIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return confirm_ready(session, match, payload.team_id, payload.pin)


@router.post("/matches/{match_id}/inducements")
def inducements(
    match_id: int,
    payload: InducementsIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return set_inducements(session, match, payload.team_id, payload.items)


@router.post("/matches/{match_id}/rolls")
def rolls(
    match_id: int,
    payload: RollsIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return apply_rolls(session, match, payload)


@router.post("/matches/{match_id}/begin")
def begin(
    match_id: int,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return begin_match(session, match)


@router.post("/matches/{match_id}/turn")
def turn(
    match_id: int,
    payload: TurnIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return set_turn(session, match, payload.turn)


@router.post("/matches/{match_id}/events")
def events(
    match_id: int,
    payload: EventIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return add_event(session, match, payload.team_id, payload.player_id, payload.event_type, payload.turn)


@router.post("/matches/{match_id}/events/undo")
def undo(
    match_id: int,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return undo_last_event(session, match)


@router.post("/matches/{match_id}/benefits")
def benefits(
    match_id: int,
    payload: BenefitIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return use_benefit(session, match, payload.team_id, payload.benefit)


@router.post("/matches/{match_id}/complete")
def complete(
    match_id: int,
    payload: CompleteIn,
    team: Team = Depends(get_current_team),
    session: Session = Depends(get_session),
) -> dict:
    match = _playable(match_id, team, session)
    return complete_match(session, match, payload)
