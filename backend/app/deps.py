from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header
from sqlmodel import Session

from app import security
from app.db import get_session
from app.errors import AuthError, ForbiddenError, NotFoundError
from app.models import Team

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_team(
    session: SessionDep,
    authorization: Annotated[Optional[str], Header()] = None,
) -> Team:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Necesitas iniciar sesion con tu equipo y PIN.")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = security.decode_token(token)
    except security.InvalidToken as exc:
        raise AuthError(str(exc)) from exc

    team = session.get(Team, payload["team_id"])
    if team is None:
        raise NotFoundError("El equipo de la sesion ya no existe.")
    return team


CurrentTeam = Annotated[Team, Depends(get_current_team)]


def require_master_key(x_master_key: Annotated[Optional[str], Header()] = None) -> bool:
    if not security.check_master_key(x_master_key):
        raise ForbiddenError("Clave de comisario invalida.")
    return True


MasterKey = Annotated[bool, Depends(require_master_key)]
