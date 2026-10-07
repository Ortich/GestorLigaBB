"""Endpoints de jugadores (subida de nivel / PE)."""

from __future__ import annotations

from fastapi import APIRouter

from app import match_service, serializers
from app.deps import CurrentTeam, SessionDep
from app.errors import ForbiddenError, LeagueError, NotFoundError
from app.models import Player, PlayerStatus
from app.schemas import LevelUpRequest, PlayerPublic

router = APIRouter(prefix="/api/players", tags=["jugadores"])


@router.post("/{player_id}/levelup", response_model=PlayerPublic)
def level_up_player(
    player_id: int,
    payload: LevelUpRequest,
    current: CurrentTeam,
    session: SessionDep,
) -> PlayerPublic:
    """Gasta PE para anadir una habilidad y subir el valor actual del jugador."""
    player = session.get(Player, player_id)
    if player is None:
        raise NotFoundError("Jugador no encontrado.")
    if player.team_id != current.id:
        raise ForbiddenError("Solo puedes mejorar jugadores de tu equipo.")
    if player.status == PlayerStatus.DEAD:
        raise LeagueError("Un jugador muerto no puede mejorar.")
    if payload.spp_cost <= 0:
        raise LeagueError("El coste en PE debe ser mayor que cero.")
    if payload.value_increase < 0:
        raise LeagueError("El incremento de valor no puede ser negativo.")

    skill = (payload.skill_name or "").strip()
    if not skill:
        raise LeagueError("Indica el nombre de la habilidad adquirida.")
    skills = serializers.split_skills(player.skills)
    if skill in skills:
        raise LeagueError(f"{player.name} ya tiene {skill}.")
    skills.append(skill)
    player.skills = ", ".join(skills)

    match_service.spend_spp(player, payload.spp_cost)
    player.current_value += payload.value_increase
    session.add(player)
    session.commit()
    session.refresh(player)
    return serializers.player_public(player)
