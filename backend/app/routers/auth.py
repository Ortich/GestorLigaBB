from __future__ import annotations

from fastapi import APIRouter
from sqlmodel import select

from app import security, serializers
from app.deps import CurrentTeam, SessionDep
from app.errors import ForbiddenError, LeagueError, NotFoundError
from app.models import Team
from app.schemas import ChangePinRequest, LoginRequest, LoginResponse, TeamDetail

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/teams")
def list_login_options(session: SessionDep) -> list[dict]:
    """Desplegable del login: solo datos publicos, nunca el PIN."""
    teams = session.exec(select(Team).order_by(Team.name)).all()
    return [
        {"id": t.id, "name": t.name, "coach_name": t.coach_name, "race": t.race, "logo": t.logo}
        for t in teams
    ]


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: SessionDep) -> LoginResponse:
    team = session.get(Team, payload.team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    if not security.verify_pin(payload.pin, team.pin_hash):
        raise ForbiddenError("PIN incorrecto.")
    return LoginResponse(
        token=security.create_token(team.id or 0, team.name),
        team_id=team.id or 0,
        team_name=team.name,
    )


@router.get("/me", response_model=TeamDetail)
def me(team: CurrentTeam, session: SessionDep) -> TeamDetail:
    return serializers.team_detail(session, team)


@router.post("/pin")
def change_pin(payload: ChangePinRequest, team: CurrentTeam, session: SessionDep) -> dict:
    if not security.verify_pin(payload.current_pin, team.pin_hash):
        raise ForbiddenError("El PIN actual no es correcto.")
    try:
        team.pin_hash = security.hash_pin(payload.new_pin)
    except ValueError as exc:
        raise LeagueError(str(exc)) from exc
    session.add(team)
    session.commit()
    return {"ok": True}
