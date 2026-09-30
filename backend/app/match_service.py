"""Maquina de estados del partido y postpartido.

SCHEDULED -> READY_CHECK -> PRE_MATCH -> IN_PROGRESS -> COMPLETED
"""

from __future__ import annotations

import random
from typing import Any, Optional

from sqlmodel import Session, select

from app import league_engine, rules, security
from app.errors import ForbiddenError, InvalidTransitionError, LeagueError, NotFoundError
from app.models import (
    LASTING_INJURY_STAT,
    MNG_RESULTS,
    PERMANENT_RESULTS,
    Bounty,
    CasualtyResult,
    EventType,
    InducementFunding,
    Match,
    MatchEvent,
    MatchInducement,
    MatchStatus,
    Player,
    PlayerStatus,
    Team,
    utcnow,
)
from app.schemas import (
    CompleteMatchRequest,
    EventRequest,
    InducementRequest,
    MatchCompletionReport,
    RollRequest,
)

ALLOWED_TRANSITIONS: dict[MatchStatus, set[MatchStatus]] = {
    MatchStatus.SCHEDULED: {MatchStatus.READY_CHECK},
    MatchStatus.READY_CHECK: {MatchStatus.PRE_MATCH, MatchStatus.SCHEDULED},
    MatchStatus.PRE_MATCH: {MatchStatus.IN_PROGRESS, MatchStatus.READY_CHECK},
    MatchStatus.IN_PROGRESS: {MatchStatus.COMPLETED, MatchStatus.PRE_MATCH},
    MatchStatus.COMPLETED: {MatchStatus.IN_PROGRESS},
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_match(session: Session, match_id: int) -> Match:
    match = session.get(Match, match_id)
    if match is None:
        raise NotFoundError(f"No existe el partido {match_id}.")
    return match


def require_participant(match: Match, team_id: int) -> None:
    if team_id not in (match.home_team_id, match.away_team_id):
        raise ForbiddenError("Ese equipo no juega este partido.")


def require_status(match: Match, *expected: MatchStatus) -> None:
    if match.status not in expected:
        names = ", ".join(s.value for s in expected)
        raise InvalidTransitionError(
            f"El partido esta en estado {match.status.value}; esta accion requiere {names}."
        )


def _other_team_id(match: Match, team_id: int) -> int:
    return match.away_team_id if team_id == match.home_team_id else match.home_team_id


# --------------------------------------------------------------------------- #
# READY CHECK
# --------------------------------------------------------------------------- #
def open_ready_check(session: Session, match: Match) -> Match:
    if match.status == MatchStatus.READY_CHECK:
        return match
    require_status(match, MatchStatus.SCHEDULED)
    match.status = MatchStatus.READY_CHECK
    match.home_ready = False
    match.away_ready = False
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def confirm_presence(session: Session, match: Match, team_id: int, pin: str) -> Match:
    require_status(match, MatchStatus.READY_CHECK)
    require_participant(match, team_id)

    team = session.get(Team, team_id)
    if team is None:
        raise NotFoundError("Equipo no encontrado.")
    if not security.verify_pin(pin, team.pin_hash):
        raise ForbiddenError("PIN incorrecto.")

    active_players = session.exec(
        select(Player).where(Player.team_id == team_id, Player.status == PlayerStatus.ACTIVE)
    ).all()
    if len(active_players) < 1:
        raise LeagueError(
            f"{team.name} no tiene jugadores disponibles. Contrata o revive jugadores antes del partido."
        )

    if team_id == match.home_team_id:
        match.home_ready = True
    else:
        match.away_ready = True

    session.add(match)
    session.commit()

    if match.home_ready and match.away_ready:
        enter_pre_match(session, match)

    session.refresh(match)
    return match


# --------------------------------------------------------------------------- #
# PRE-MATCH
# --------------------------------------------------------------------------- #
def enter_pre_match(session: Session, match: Match) -> Match:
    require_status(match, MatchStatus.READY_CHECK)
    if not (match.home_ready and match.away_ready):
        raise InvalidTransitionError("Ambos entrenadores deben confirmar su PIN antes del prepartido.")

    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:
        raise NotFoundError("Equipo no encontrado.")

    home_ctv = league_engine.compute_ctv(session, home).total
    away_ctv = league_engine.compute_ctv(session, away).total
    amount, beneficiary = league_engine.petty_cash_for(home_ctv, away_ctv, home.id, away.id)

    match.home_ctv = home_ctv
    match.away_ctv = away_ctv
    match.petty_cash_amount = amount
    match.petty_cash_team_id = beneficiary
    match.status = MatchStatus.PRE_MATCH

    if match.bounty_id is None:
        state = league_engine.get_league_state(session)
        match.bounty_id = state.active_bounty_id

    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def _spent_petty_cash(session: Session, match_id: int) -> int:
    items = session.exec(select(MatchInducement).where(MatchInducement.match_id == match_id)).all()
    return sum(i.total_cost for i in items)


def add_inducement(session: Session, match: Match, req: InducementRequest) -> MatchInducement:
    require_status(match, MatchStatus.PRE_MATCH)
    require_participant(match, req.team_id)

    if match.petty_cash_team_id is None:
        raise LeagueError("Las VAE estan igualadas: no hay Fondo Menor y no se pueden comprar incentivos.")
    if req.team_id != match.petty_cash_team_id:
        raise ForbiddenError(
            "Solo el equipo con menor VAE puede comprar incentivos, y unicamente con su Fondo Menor."
        )
    if req.quantity < 1:
        raise LeagueError("La cantidad debe ser al menos 1.")

    catalog_item = rules.inducement_by_code(req.code)
    if catalog_item is None:
        raise NotFoundError(f"El incentivo '{req.code}' no existe en el catalogo.")

    unit_cost = int(req.unit_cost if req.unit_cost is not None else catalog_item.get("cost", 0))
    if unit_cost <= 0:
        raise LeagueError(
            f"'{catalog_item['name']}' tiene coste variable: indica el coste unitario segun su ficha."
        )

    existing = session.exec(
        select(MatchInducement).where(
            MatchInducement.match_id == match.id,
            MatchInducement.team_id == req.team_id,
            MatchInducement.code == req.code,
        )
    ).first()

    max_allowed = int(catalog_item.get("max", 99))
    already = existing.quantity if existing else 0
    if already + req.quantity > max_allowed:
        raise LeagueError(
            f"Maximo {max_allowed} x {catalog_item['name']} por partido (ya tienes {already})."
        )

    extra_cost = unit_cost * req.quantity
    remaining = match.petty_cash_amount - _spent_petty_cash(session, match.id)
    if extra_cost > remaining:
        raise LeagueError(
            f"Fondo Menor insuficiente: quedan {remaining:,} mo y el pedido cuesta {extra_cost:,} mo."
        )

    if existing:
        existing.quantity += req.quantity
        existing.unit_cost = unit_cost
        existing.total_cost = existing.quantity * unit_cost
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    item = MatchInducement(
        match_id=match.id,
        team_id=req.team_id,
        code=req.code,
        name=catalog_item["name"],
        quantity=req.quantity,
        unit_cost=unit_cost,
        total_cost=unit_cost * req.quantity,
        funding=InducementFunding.PETTY_CASH,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def remove_inducement(session: Session, match: Match, inducement_id: int) -> None:
    require_status(match, MatchStatus.PRE_MATCH)
    item = session.get(MatchInducement, inducement_id)
    if item is None or item.match_id != match.id:
        raise NotFoundError("Incentivo no encontrado en este partido.")
    session.delete(item)
    session.commit()


_ROLL_KINDS = {"WEATHER", "PRAYER", "KICK_OFF"}


def record_roll(session: Session, match: Match, req: RollRequest, rng: Optional[random.Random] = None) -> Match:
    require_status(match, MatchStatus.PRE_MATCH)
    kind = (req.kind or "").upper()
    if kind not in _ROLL_KINDS:
        raise LeagueError(f"Tirada desconocida '{req.kind}'. Usa WEATHER, PRAYER o KICK_OFF.")

    if kind == "WEATHER":
        value = req.value if req.value is not None else league_engine.roll_2d6(rng)
        if not 2 <= value <= 12:
            raise LeagueError("La tirada de clima es 2D6: valores de 2 a 12.")
        entry = rules.weather_entry(value)
        match.weather_roll = value
        match.weather_result = entry["name"] if entry else None
    elif kind == "PRAYER":
        value = req.value if req.value is not None else league_engine.roll_d16(rng)
        if not 1 <= value <= 16:
            raise LeagueError("La tirada de Plegarias a Nuffle es 1D16: valores de 1 a 16.")
        entry = rules.prayer_entry(value)
        match.prayer_roll = value
        match.prayer_result = entry["name"] if entry else None
        if req.team_id is not None:
            require_participant(match, req.team_id)
            match.prayer_team_id = req.team_id
    else:
        value = req.value if req.value is not None else league_engine.roll_2d6(rng)
        if not 2 <= value <= 12:
            raise LeagueError("La tirada de patada inicial es 2D6: valores de 2 a 12.")
        entry = rules.kick_off_entry(value)
        match.kick_off_roll = value
        match.kick_off_result = entry["name"] if entry else None

    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def start_match(session: Session, match: Match) -> Match:
    require_status(match, MatchStatus.PRE_MATCH)
    if match.weather_roll is None:
        raise InvalidTransitionError("Tira el clima antes de empezar el partido.")
    match.status = MatchStatus.IN_PROGRESS
    match.started_at = match.started_at or utcnow()
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


# --------------------------------------------------------------------------- #
# IN PROGRESS
# --------------------------------------------------------------------------- #
def add_event(session: Session, match: Match, req: EventRequest) -> MatchEvent:
    require_status(match, MatchStatus.IN_PROGRESS)
    require_participant(match, req.team_id)

    player: Optional[Player] = None
    if req.player_id is not None:
        player = session.get(Player, req.player_id)
        if player is None:
            raise NotFoundError("Jugador no encontrado.")
        if player.team_id != req.team_id:
            raise LeagueError("El jugador no pertenece al equipo indicado.")

    victim: Optional[Player] = None
    if req.event_type == EventType.CAS:
        if req.victim_player_id is not None:
            victim = session.get(Player, req.victim_player_id)
            if victim is None:
                raise NotFoundError("El jugador lesionado no existe.")
            if victim.team_id != _other_team_id(match, req.team_id):
                raise LeagueError("El jugador lesionado debe pertenecer al equipo rival.")

    spp = rules.spp_for(req.event_type.value) if player is not None else 0

    event = MatchEvent(
        match_id=match.id,
        team_id=req.team_id,
        player_id=req.player_id,
        event_type=req.event_type,
        turn=req.turn,
        spp_awarded=spp,
        victim_player_id=req.victim_player_id,
        casualty_result=req.casualty_result,
        note=req.note or "",
    )
    session.add(event)

    if player is not None and spp:
        player.spp += spp
        session.add(player)

    if req.event_type == EventType.TD:
        if req.team_id == match.home_team_id:
            match.home_td += 1
        else:
            match.away_td += 1
        session.add(match)

    session.commit()
    session.refresh(event)
    return event


def delete_event(session: Session, event_id: int) -> None:
    event = session.get(MatchEvent, event_id)
    if event is None:
        raise NotFoundError("Evento no encontrado.")

    match = session.get(Match, event.match_id)
    if event.player_id and event.spp_awarded:
        player = session.get(Player, event.player_id)
        if player is not None:
            player.spp = max(0, player.spp - event.spp_awarded)
            session.add(player)

    if match is not None and event.event_type == EventType.TD:
        if event.team_id == match.home_team_id:
            match.home_td = max(0, match.home_td - 1)
        else:
            match.away_td = max(0, match.away_td - 1)
        session.add(match)

    session.delete(event)
    session.commit()


# --------------------------------------------------------------------------- #
# COMPLETED
# --------------------------------------------------------------------------- #
def _apply_lasting_injury(player: Player, result: CasualtyResult) -> Optional[str]:
    stat = LASTING_INJURY_STAT.get(result)
    if stat is None:
        return None
    # MA y ST empeoran bajando; AG, PA y AV son objetivos de dado y empeoran subiendo
    # el numero necesario (AV es al reves: baja el valor de armadura).
    if stat == "ma":
        player.ma = max(1, player.ma - 1)
        return "-1 MA"
    if stat == "st":
        player.st = max(1, player.st - 1)
        return "-1 ST"
    if stat == "ag":
        player.ag = min(6, player.ag + 1)
        return "-1 AG"
    if stat == "pa":
        if player.pa is None:
            return None
        player.pa = min(6, player.pa + 1)
        return "-1 PA"
    if stat == "av":
        player.av = max(3, player.av - 1)
        return "-1 AV"
    return None


def complete_match(
    session: Session,
    match: Match,
    req: CompleteMatchRequest,
    rng: Optional[random.Random] = None,
) -> MatchCompletionReport:
    require_status(match, MatchStatus.IN_PROGRESS)

    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:
        raise NotFoundError("Equipo no encontrado.")

    post = rules.post_match_config()
    multiplier = int(post.get("winnings_multiplier", 10_000))

    # 1. Ganancias: D6 x 10.000 mo
    home_roll = req.home_winnings_roll if req.home_winnings_roll is not None else league_engine.roll_d6(rng)
    away_roll = req.away_winnings_roll if req.away_winnings_roll is not None else league_engine.roll_d6(rng)
    for label, value in (("local", home_roll), ("visitante", away_roll)):
        if not 1 <= value <= 6:
            raise LeagueError(f"La tirada de ganancias del equipo {label} debe estar entre 1 y 6.")

    match.home_winnings_roll = home_roll
    match.away_winnings_roll = away_roll
    match.home_winnings = home_roll * multiplier
    match.away_winnings = away_roll * multiplier
    home.treasury += match.home_winnings
    away.treasury += match.away_winnings

    # 2. MVP: 4 SPP
    mvp_spp = rules.spp_for("MVP")
    for team, player_id, field in (
        (home, req.home_mvp_player_id, "home_mvp_player_id"),
        (away, req.away_mvp_player_id, "away_mvp_player_id"),
    ):
        if player_id is None:
            continue
        player = session.get(Player, player_id)
        if player is None or player.team_id != team.id:
            raise LeagueError(f"El MVP indicado no pertenece a {team.name}.")
        player.spp += mvp_spp
        session.add(player)
        setattr(match, field, player_id)
        session.add(
            MatchEvent(
                match_id=match.id,
                team_id=team.id,
                player_id=player_id,
                event_type=EventType.MVP,
                spp_awarded=mvp_spp,
                note="MVP del partido",
            )
        )

    # 3. Jugadores que ya cumplieron su sancion vuelven a estar disponibles
    recovered: list[dict[str, Any]] = []
    for team in (home, away):
        players = session.exec(
            select(Player).where(Player.team_id == team.id, Player.status == PlayerStatus.MNG)
        ).all()
        for player in players:
            if player.mng_match_id == match.id:
                continue
            player.status = PlayerStatus.ACTIVE
            player.mng_match_id = None
            session.add(player)
            recovered.append({"player_id": player.id, "player_name": player.name, "team_id": team.id})

    # 4. Lesiones registradas en este partido
    state = league_engine.get_league_state(session)
    mercy_active = league_engine.rookie_safety_active(match.round_number, state)
    injuries: list[dict[str, Any]] = []
    payouts: list[dict[str, Any]] = []

    cas_events = session.exec(
        select(MatchEvent).where(
            MatchEvent.match_id == match.id, MatchEvent.event_type == EventType.CAS
        ).order_by(MatchEvent.id)
    ).all()

    for event in cas_events:
        if event.victim_player_id is None or event.casualty_result is None:
            continue
        victim = session.get(Player, event.victim_player_id)
        if victim is None or victim.status == PlayerStatus.DEAD:
            continue

        result = event.casualty_result
        detail = {
            "player_id": victim.id,
            "player_name": victim.name,
            "team_id": victim.team_id,
            "result": result.value,
            "effect": "",
        }

        if result == CasualtyResult.DEAD:
            victim.status = PlayerStatus.DEAD
            detail["effect"] = "Muerto"
        elif result in MNG_RESULTS:
            victim.status = PlayerStatus.MNG
            victim.mng_match_id = match.id
            effect = _apply_lasting_injury(victim, result)
            if result == CasualtyResult.SERIOUS_INJURY:
                victim.niggling_injuries += 1
                effect = "Lesion persistente"
            detail["effect"] = effect or "Se pierde el proximo partido"
        else:
            detail["effect"] = "Sin secuelas"

        session.add(victim)
        injuries.append(detail)

        if mercy_active and result in PERMANENT_RESULTS:
            victim_team = session.get(Team, victim.team_id)
            if victim_team is not None:
                percentage = league_engine.rookie_safety_percentage(victim_team.rookie_safety_claims)
                payout = league_engine.rookie_safety_payout(
                    victim_team.rookie_safety_claims, victim.current_value
                )
                victim_team.treasury += payout
                victim_team.rookie_safety_claims += 1
                session.add(victim_team)
                payouts.append(
                    {
                        "team_id": victim_team.id,
                        "team_name": victim_team.name,
                        "player_name": victim.name,
                        "percentage": percentage,
                        "gold": payout,
                    }
                )

    # 5. Recompensa semanal
    bounty_payout = None
    if req.bounty_winner_team_id is not None:
        require_participant(match, req.bounty_winner_team_id)
        bounty = session.get(Bounty, match.bounty_id) if match.bounty_id else None
        if bounty is not None:
            winner = home if req.bounty_winner_team_id == home.id else away
            winner.treasury += bounty.reward_gold
            match.bounty_winner_team_id = winner.id
            session.add(winner)
            bounty_payout = {
                "team_id": winner.id,
                "team_name": winner.name,
                "bounty": bounty.name,
                "gold": bounty.reward_gold,
            }

    match.status = MatchStatus.COMPLETED
    match.completed_at = utcnow()
    session.add_all([match, home, away])
    session.commit()

    assignments = _after_match_completed(session, match)

    return MatchCompletionReport(
        match_id=match.id or 0,
        home_winnings=match.home_winnings,
        away_winnings=match.away_winnings,
        injuries=injuries,
        rookie_safety_payouts=payouts,
        bounty_payout=bounty_payout,
        recovered_players=recovered,
        sponsors=assignments,
    )


def _after_match_completed(session: Session, match: Match):
    """Avanza la jornada si procede y reevalua los patrocinadores."""
    state = league_engine.get_league_state(session)
    round_matches = session.exec(
        select(Match).where(Match.round_number == state.current_round)
    ).all()
    if round_matches and all(m.status == MatchStatus.COMPLETED for m in round_matches):
        if state.current_round < state.total_rounds:
            state.current_round += 1
            session.add(state)
            session.commit()

    return league_engine.assign_sponsors(session, apply=True)


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
def force_status(session: Session, match: Match, status: MatchStatus) -> Match:
    match.status = status
    if status in (MatchStatus.SCHEDULED, MatchStatus.READY_CHECK):
        match.home_ready = False
        match.away_ready = False
    if status != MatchStatus.COMPLETED:
        match.completed_at = None
    session.add(match)
    session.commit()
    session.refresh(match)
    return match
