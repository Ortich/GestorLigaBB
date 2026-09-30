from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlmodel import select

from app import rules, serializers
from app.deps import CurrentTeam, SessionDep
from app.errors import ForbiddenError, LeagueError, NotFoundError
from app.models import Player, PlayerStatus, Team
from app.schemas import (
    AdvancementRequest,
    HirePlayerRequest,
    StaffPurchaseRequest,
    TeamDetail,
    TeamSummary,
    TeamUpdate,
)

router = APIRouter(prefix="/api/teams", tags=["equipos"])

_STAT_ADVANCEMENTS = {
    "STAT_MA_AV": ("ma", "av"),
    "STAT_PA": ("pa",),
    "STAT_AG": ("ag",),
    "STAT_ST": ("st",),
}


@router.get("", response_model=list[TeamSummary])
def list_teams(session: SessionDep) -> list[TeamSummary]:
    teams = session.exec(select(Team).order_by(Team.name)).all()
    return [serializers.team_summary(session, t) for t in teams]


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: int, session: SessionDep) -> TeamDetail:
    team = session.get(Team, team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    return serializers.team_detail(session, team)


def _on_roster(player: Player) -> bool:
    """Muertos y despedidos no ocupan plaza ni cuentan para el maximo de la posicion."""
    return player.status not in (PlayerStatus.DEAD, PlayerStatus.RETIRED)


def _assert_own_team(current: Team, team_id: int) -> None:
    if current.id != team_id:
        raise ForbiddenError("Solo puedes modificar tu propio equipo.")


@router.patch("/{team_id}", response_model=TeamDetail)
def update_team(team_id: int, payload: TeamUpdate, current: CurrentTeam, session: SessionDep) -> TeamDetail:
    _assert_own_team(current, team_id)
    if payload.coach_name is not None:
        current.coach_name = payload.coach_name.strip()[:60]
    if payload.logo is not None:
        current.logo = payload.logo.strip()[:8]
    if payload.sponsor_preference is not None:
        valid = {s["code"] for s in rules.sponsor_definitions()}
        unknown = [c for c in payload.sponsor_preference if c not in valid]
        if unknown:
            raise LeagueError(f"Patrocinadores desconocidos: {', '.join(unknown)}")
        current.sponsor_preference = ",".join(payload.sponsor_preference)
    session.add(current)
    session.commit()
    session.refresh(current)
    return serializers.team_detail(session, current)


@router.get("/{team_id}/roster-options")
def roster_options(team_id: int, session: SessionDep) -> dict[str, Any]:
    """Posiciones contratables para la raza del equipo, con huecos restantes."""
    team = session.get(Team, team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    race = rules.load_rosters()["races"].get(team.race)
    if race is None:
        return {"race": team.race, "positions": [], "reroll_cost": team.reroll_cost}

    players = session.exec(select(Player).where(Player.team_id == team_id)).all()
    alive = [p for p in players if _on_roster(p)]
    positions = []
    for position in race["positions"]:
        used = sum(1 for p in alive if p.position == position["name"])
        positions.append({**position, "used": used, "remaining": max(0, position["max"] - used)})
    return {
        "race": team.race,
        "reroll_cost": race.get("reroll_cost", team.reroll_cost),
        "positions": positions,
        "roster_size": len(alive),
    }


@router.post("/{team_id}/players", response_model=TeamDetail)
def hire_player(
    team_id: int, payload: HirePlayerRequest, current: CurrentTeam, session: SessionDep
) -> TeamDetail:
    _assert_own_team(current, team_id)
    race = rules.load_rosters()["races"].get(current.race)
    if race is None:
        raise LeagueError(f"No hay plantilla definida para la raza {current.race}.")

    position = next((p for p in race["positions"] if p["code"] == payload.position_code), None)
    if position is None:
        raise NotFoundError(f"La posicion '{payload.position_code}' no existe en esta raza.")

    players = session.exec(select(Player).where(Player.team_id == team_id)).all()
    alive = [p for p in players if _on_roster(p)]
    if len(alive) >= 16:
        raise LeagueError("La plantilla ya tiene 16 jugadores, el maximo permitido.")
    if sum(1 for p in alive if p.position == position["name"]) >= position["max"]:
        raise LeagueError(f"Ya tienes el maximo de {position['name']} ({position['max']}).")
    if current.treasury < position["cost"]:
        raise LeagueError(
            f"Tesoreria insuficiente: necesitas {position['cost']:,} mo y tienes {current.treasury:,} mo."
        )

    used_numbers = {p.number for p in players}
    number = payload.number or next(n for n in range(1, 17) if n not in used_numbers)
    if number in used_numbers:
        raise LeagueError(f"El dorsal {number} ya esta ocupado.")

    current.treasury -= position["cost"]
    session.add(current)
    session.add(
        Player(
            team_id=team_id,
            number=number,
            name=payload.name.strip()[:40] or position["name"],
            position=position["name"],
            ma=position["ma"],
            st=position["st"],
            ag=position["ag"],
            pa=position.get("pa"),
            av=position["av"],
            skills=", ".join(position.get("skills", [])),
            cost=position["cost"],
            current_value=position["cost"],
        )
    )
    session.commit()
    session.refresh(current)
    return serializers.team_detail(session, current)


@router.delete("/{team_id}/players/{player_id}", response_model=TeamDetail)
def fire_player(team_id: int, player_id: int, current: CurrentTeam, session: SessionDep) -> TeamDetail:
    _assert_own_team(current, team_id)
    player = session.get(Player, player_id)
    if player is None or player.team_id != team_id:
        raise NotFoundError("Jugador no encontrado en tu plantilla.")
    if player.status == PlayerStatus.DEAD:
        raise LeagueError(
            f"{player.name} ha muerto. Eso no se despide: en las jornadas 1 y 2 "
            "la Red de Seguridad ya devuelve su valor actual."
        )
    if player.status == PlayerStatus.RETIRED:
        raise LeagueError(f"{player.name} ya esta despedido.")

    # El despido devuelve el coste de contratacion, sin las mejoras.
    current.treasury += player.cost
    player.status = PlayerStatus.RETIRED
    session.add(player)
    session.add(current)
    session.commit()
    session.refresh(current)
    return serializers.team_detail(session, current)


@router.post("/{team_id}/players/{player_id}/advance", response_model=TeamDetail)
def advance_player(
    team_id: int,
    player_id: int,
    payload: AdvancementRequest,
    current: CurrentTeam,
    session: SessionDep,
) -> TeamDetail:
    _assert_own_team(current, team_id)
    player = session.get(Player, player_id)
    if player is None or player.team_id != team_id:
        raise NotFoundError("Jugador no encontrado en tu plantilla.")
    if player.status == PlayerStatus.DEAD:
        raise LeagueError("Un jugador muerto no puede mejorar.")

    advancement = rules.advancement_by_code(payload.code)
    if advancement is None:
        raise NotFoundError(f"La mejora '{payload.code}' no existe.")
    if player.spp < advancement["spp"]:
        raise LeagueError(
            f"{player.name} tiene {player.spp} SPP y esta mejora cuesta {advancement['spp']} SPP."
        )

    if payload.code in _STAT_ADVANCEMENTS:
        allowed = _STAT_ADVANCEMENTS[payload.code]
        stat = (payload.stat or allowed[0]).lower()
        if stat not in allowed:
            raise LeagueError(f"Esta mejora solo permite modificar: {', '.join(allowed)}.")
        if stat in ("ma", "st"):
            setattr(player, stat, getattr(player, stat) + 1)
        elif stat == "av":
            player.av += 1
        else:  # ag / pa: mejorar significa bajar el numero objetivo
            value = getattr(player, stat)
            if value is None:
                raise LeagueError("Este jugador no tiene esa caracteristica.")
            setattr(player, stat, max(1, value - 1))
    else:
        skill = (payload.skill or "").strip()
        if not skill:
            raise LeagueError("Indica el nombre de la habilidad adquirida.")
        skills = serializers.split_skills(player.skills)
        if skill in skills:
            raise LeagueError(f"{player.name} ya tiene {skill}.")
        skills.append(skill)
        player.skills = ", ".join(skills)

    player.spp -= advancement["spp"]
    player.current_value += advancement["value"]
    session.add(player)
    session.commit()
    session.refresh(current)
    return serializers.team_detail(session, current)


@router.post("/{team_id}/staff", response_model=TeamDetail)
def buy_staff(
    team_id: int, payload: StaffPurchaseRequest, current: CurrentTeam, session: SessionDep
) -> TeamDetail:
    _assert_own_team(current, team_id)
    if payload.quantity == 0:
        raise LeagueError("Indica una cantidad distinta de cero.")

    costs = rules.ctv_costs()
    prices = {
        "REROLL": current.reroll_cost * 2,  # Fuera de la creacion del equipo cuestan el doble
        "ASSISTANT_COACH": costs["assistant_coach"],
        "CHEERLEADER": costs["cheerleader"],
        "APOTHECARY": costs["apothecary"],
        "FAN": 10_000,
    }
    item = payload.item.upper()
    if item not in prices:
        raise NotFoundError(f"Elemento '{payload.item}' desconocido.")

    total = prices[item] * payload.quantity
    if total > 0 and current.treasury < total:
        raise LeagueError(
            f"Tesoreria insuficiente: necesitas {total:,} mo y tienes {current.treasury:,} mo."
        )

    if item == "REROLL":
        if current.rerolls + payload.quantity < 0 or current.rerolls + payload.quantity > 8:
            raise LeagueError("Puedes tener entre 0 y 8 Segundas Oportunidades.")
        current.rerolls += payload.quantity
    elif item == "ASSISTANT_COACH":
        current.assistant_coaches = max(0, current.assistant_coaches + payload.quantity)
    elif item == "CHEERLEADER":
        current.cheerleaders = max(0, current.cheerleaders + payload.quantity)
    elif item == "FAN":
        current.fans = max(1, current.fans + payload.quantity)
    else:
        if current.apothecary and payload.quantity > 0:
            raise LeagueError("Ya tienes Apotecario.")
        current.apothecary = payload.quantity > 0
        total = prices[item] if payload.quantity > 0 else 0

    current.treasury -= max(0, total)
    session.add(current)
    session.commit()
    session.refresh(current)
    return serializers.team_detail(session, current)
