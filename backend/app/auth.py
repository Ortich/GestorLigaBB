from __future__ import annotations

import hmac
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.database import get_session
from app.models import Team

SECRET = os.environ.get("BB_SECRET", "bloodbowl-mesa-local")
MASTER_KEY = os.environ.get("MASTER_KEY", "nuffle")
TOKEN_TTL = 60 * 60 * 24 * 14
bearer = HTTPBearer(auto_error=False)


class RuleError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def make_token(subject: str) -> str:
    expires = int(time.time()) + TOKEN_TTL
    payload = f"{subject}|{expires}"
    signature = hmac.new(SECRET.encode(), payload.encode(), hashlib_sha256()).hexdigest()
    return f"{payload}|{signature}"


def hashlib_sha256():
    import hashlib

    return hashlib.sha256


def read_subject(token: str) -> str:
    try:
        subject, expires, signature = token.split("|")
        payload = f"{subject}|{expires}"
        expected = hmac.new(SECRET.encode(), payload.encode(), hashlib_sha256()).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise RuleError("Sesión no válida.", 401)
        if int(expires) < time.time():
            raise RuleError("La sesión ha caducado. Vuelve a entrar.", 401)
        return subject
    except RuleError:
        raise
    except Exception as exc:  # token mal formado
        raise RuleError("Sesión no válida.", 401) from exc


def require_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Necesitas entrar con tu equipo y tu PIN.")
    try:
        return read_subject(credentials.credentials)
    except RuleError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message) from exc


def get_current_team(
    subject: str = Depends(require_subject),
    session: Session = Depends(get_session),
) -> Team:
    if not subject.startswith("team:"):
        raise HTTPException(status_code=401, detail="Esta acción es del entrenador, no del comisario.")
    try:
        team_id = int(subject.split(":", 1)[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Sesión no válida.") from exc
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status_code=401, detail="Ese equipo ya no está en la liga.")
    return team


def require_admin(subject: str = Depends(require_subject)) -> str:
    if subject != "admin":
        raise HTTPException(status_code=401, detail="Hace falta la llave del comisario.")
    return subject


def check_master_key(value: str) -> None:
    if not hmac.compare_digest(value, MASTER_KEY):
        raise RuleError("Llave de comisario incorrecta.", 401)


def check_pin(team: Team, pin: str) -> None:
    if not (len(pin) == 4 and pin.isdigit() and hmac.compare_digest(team.pin, pin)):
        raise RuleError("PIN incorrecto.", 401)
