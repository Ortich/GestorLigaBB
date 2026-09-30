from __future__ import annotations


class LeagueError(Exception):
    """Error de negocio: se traduce a una respuesta HTTP clara."""

    status_code = 400

    def __init__(self, message: str, status_code: int | None = None, code: str = "league_error"):
        super().__init__(message)
        self.message = message
        self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(LeagueError):
    status_code = 404

    def __init__(self, message: str):
        super().__init__(message, code="not_found")


class AuthError(LeagueError):
    status_code = 401

    def __init__(self, message: str):
        super().__init__(message, code="unauthorized")


class ForbiddenError(LeagueError):
    status_code = 403

    def __init__(self, message: str):
        super().__init__(message, code="forbidden")


class InvalidTransitionError(LeagueError):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message, code="invalid_transition")
