from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlmodel import or_, select

from app import match_service, serializers
from app.deps import CurrentTeam, SessionDep
from app.errors import ForbiddenError, NotFoundError
from app.models import Match, MatchEvent, MatchStatus, Team
from app.schemas import (
    CompleteMatchRequest,
    EventRequest,
    InducementRequest,
    MatchCompletionReport,
    MatchDetail,
    MatchSummary,
    ReadyCheckRequest,
    RollRequest,
)

router = APIRouter(prefix="/api/matches", tags=["partidos"])

_OPEN_STATUSES = (
    MatchStatus.SCHEDULED,
    MatchStatus.READY_CHECK,
    MatchStatus.PRE_MATCH,
    MatchStatus.IN_PROGRESS,
)


def _load(session: SessionDep, match_id: int) -> Match:
    return match_service.get_match(session, match_id)


def _guard(match: Match, team: Team) -> None:
    if team.id not in (match.home_team_id, match.away_team_id):
        raise ForbiddenError("Solo los dos equipos implicados pueden gestionar este partido.")


@router.get("", response_model=list[MatchSummary])
def list_matches(
    session: SessionDep,
    round_number: Optional[int] = Query(default=None, alias="round"),
    team_id: Optional[int] = None,
    status: Optional[MatchStatus] = None,
) -> list[MatchSummary]:
    statement = select(Match).order_by(Match.round_number, Match.id)
    if round_number is not None:
        statement = statement.where(Match.round_number == round_number)
    if team_id is not None:
        statement = statement.where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
        )
    if status is not None:
        statement = statement.where(Match.status == status)
    return [serializers.match_summary(session, m) for m in session.exec(statement).all()]


@router.get("/next", response_model=Optional[MatchSummary])
def next_match(session: SessionDep, team_id: int) -> Optional[MatchSummary]:
    statement = (
        select(Match)
        .where(
            or_(Match.home_team_id == team_id, Match.away_team_id == team_id),
            Match.status.in_(_OPEN_STATUSES),
        )
        .order_by(Match.round_number, Match.id)
    )
    match = session.exec(statement).first()
    return serializers.match_summary(session, match) if match else None


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, session: SessionDep) -> MatchDetail:
    return serializers.match_detail(session, _load(session, match_id))


@router.post("/{match_id}/ready-check", response_model=MatchDetail)
def open_ready_check(match_id: int, team: CurrentTeam, session: SessionDep) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    return serializers.match_detail(session, match_service.open_ready_check(session, match))


@router.post("/{match_id}/confirm", response_model=MatchDetail)
def confirm(
    match_id: int, payload: ReadyCheckRequest, team: CurrentTeam, session: SessionDep
) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    return serializers.match_detail(
        session, match_service.confirm_presence(session, match, payload.team_id, payload.pin)
    )


@router.post("/{match_id}/inducements", response_model=MatchDetail)
def add_inducement(
    match_id: int, payload: InducementRequest, team: CurrentTeam, session: SessionDep
) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    match_service.add_inducement(session, match, payload)
    return serializers.match_detail(session, match)


@router.delete("/{match_id}/inducements/{inducement_id}", response_model=MatchDetail)
def remove_inducement(
    match_id: int, inducement_id: int, team: CurrentTeam, session: SessionDep
) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    match_service.remove_inducement(session, match, inducement_id)
    return serializers.match_detail(session, match)


@router.post("/{match_id}/rolls", response_model=MatchDetail)
def roll(match_id: int, payload: RollRequest, team: CurrentTeam, session: SessionDep) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    return serializers.match_detail(session, match_service.record_roll(session, match, payload))


@router.post("/{match_id}/start", response_model=MatchDetail)
def start(match_id: int, team: CurrentTeam, session: SessionDep) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    return serializers.match_detail(session, match_service.start_match(session, match))


@router.post("/{match_id}/events", response_model=MatchDetail)
def add_event(
    match_id: int, payload: EventRequest, team: CurrentTeam, session: SessionDep
) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    match_service.add_event(session, match, payload)
    session.refresh(match)
    return serializers.match_detail(session, match)


@router.delete("/{match_id}/events/{event_id}", response_model=MatchDetail)
def delete_event(
    match_id: int, event_id: int, team: CurrentTeam, session: SessionDep
) -> MatchDetail:
    match = _load(session, match_id)
    _guard(match, team)
    event = session.get(MatchEvent, event_id)
    if event is None or event.match_id != match.id:
        raise NotFoundError("Evento no encontrado en este partido.")
    match_service.delete_event(session, event_id)
    session.refresh(match)
    return serializers.match_detail(session, match)


@router.post("/{match_id}/complete", response_model=MatchCompletionReport)
def complete(
    match_id: int, payload: CompleteMatchRequest, team: CurrentTeam, session: SessionDep
) -> MatchCompletionReport:
    match = _load(session, match_id)
    _guard(match, team)
    return match_service.complete_match(session, match, payload)
