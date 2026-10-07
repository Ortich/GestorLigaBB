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

# Eventos que otorgan PE y por tanto exigen saber quien los realiza.
EVENTS_REQUIRING_PLAYER = {
    EventType.TD,
    EventType.CAS,
    EventType.PASS,
    EventType.INT,
    EventType.FOUL,
    EventType.DEFLECTION,
    EventType.INJURY,
}

# Prioridad de interaccion para nominar MVP: TD > bloqueos > pases > faltas.
MVP_INTERACTION_ORDER = (EventType.TD, EventType.CAS, EventType.PASS, EventType.FOUL)


def award_spp(player: Player, amount: int) -> None:
    """Suma PE ganados y mantiene sincronizado el disponible."""
    if amount <= 0:
        return
    player.spp_earned += amount
    player.spp += amount


def revoke_spp(player: Player, amount: int) -> None:
    """Revierte PE de un evento borrado (solo de lo ganado, no de lo gastado)."""
    if amount <= 0:
        return
    player.spp_earned = max(0, player.spp_earned - amount)
    player.spp = max(0, player.spp_available)


def spend_spp(player: Player, amount: int) -> None:
    """Gasta PE disponibles en una mejora."""
    if amount <= 0:
        return
    if player.spp_available < amount:
        raise LeagueError(
            f"{player.name} tiene {player.spp_available} PE y esta mejora cuesta {amount} PE."
        )
    player.spp_spent += amount
    player.spp = player.spp_available


def spp_for_event(event_type: EventType, *, player: Optional[Player], is_block_casualty: bool) -> int:
    if player is None:
        return 0
    if event_type == EventType.INJURY:
        return 0
    if event_type == EventType.CAS:
        # Bloqueo/Blitz: siempre PE si hay causante. Legacy: respeta el flag.
        return rules.spp_for("CAS") if is_block_casualty else 0
    return rules.spp_for(event_type.value)


def interaction_score(events: list[MatchEvent], player_id: int) -> tuple[int, int, int, int]:
    """(TD, bloqueos, pases, faltas) — mayor = mas interaccion para el MVP."""
    td = cas = passes = fouls = 0
    for event in events:
        if event.player_id != player_id:
            continue
        if event.event_type == EventType.TD:
            td += 1
        elif event.event_type == EventType.CAS and event.is_block_casualty:
            cas += 1
        elif event.event_type == EventType.PASS:
            passes += 1
        elif event.event_type == EventType.FOUL:
            fouls += 1
    return (td, cas, passes, fouls)


def mvp_candidates(
    session: Session,
    match: Match,
    team_id: int,
    *,
    limit: int = 3,
) -> list[Player]:
    """Hasta `limit` jugadores del equipo ordenados por interaccion en el partido."""
    players = session.exec(
        select(Player).where(Player.team_id == team_id).order_by(Player.number)
    ).all()
    eligible = [p for p in players if p.status != PlayerStatus.RETIRED and p.id is not None]
    events = session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id, MatchEvent.team_id == team_id)
    ).all()

    scored = sorted(
        eligible,
        key=lambda p: (
            tuple(-n for n in interaction_score(events, p.id or 0)),
            p.number or 0,
        ),
    )
    return scored[:limit]


def pick_mvp_player_id(
    session: Session,
    match: Match,
    team: Team,
    *,
    mode: str,
    player_id: Optional[int],
    rng: random.Random,
) -> int:
    """Resuelve el MVP: automatico (1D3 entre top 3) o elegido entre los candidatos."""
    candidates = mvp_candidates(session, match, team.id or 0)
    if not candidates:
        raise LeagueError(f"{team.name} no tiene jugadores elegibles para el MVP.")
    candidate_ids = {p.id for p in candidates if p.id is not None}

    mode_norm = (mode or "").strip().lower()
    if not mode_norm:
        # Compat API: si mandan player_id sin modo, es eleccion manual.
        mode_norm = "pick" if player_id is not None else "auto"

    if mode_norm in ("auto", "automatic", "automatico"):
        chosen = rng.choice(candidates)
        assert chosen.id is not None
        return chosen.id

    if mode_norm in ("pick", "manual", "rival", "opponent"):
        if player_id is None:
            raise LeagueError(
                f"Indica el MVP de {team.name} entre los {len(candidates)} candidatos."
            )
        if player_id not in candidate_ids:
            names = ", ".join(f"#{p.number} {p.name}" for p in candidates)
            raise LeagueError(f"El MVP de {team.name} debe ser uno de: {names}.")
        return player_id

    raise LeagueError(f"Modo de MVP desconocido: {mode}. Usa 'auto' o 'pick'.")


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

    if req.event_type in EVENTS_REQUIRING_PLAYER and req.player_id is None:
        raise LeagueError(
            f"Indica que jugador realiza el {req.event_type.value}: hace falta para el acta y los PE."
        )

    player: Optional[Player] = None
    if req.player_id is not None:
        player = session.get(Player, req.player_id)
        if player is None:
            raise NotFoundError("Jugador no encontrado.")
        if player.team_id != req.team_id:
            raise LeagueError("El jugador no pertenece al equipo indicado.")

    victim: Optional[Player] = None
    is_block = False

    if req.event_type == EventType.CAS:
        # Bloqueo/Blitz: siempre da PE; el causante es obligatorio.
        is_block = True
        if player is None:
            raise LeagueError("Un bloqueo necesita al jugador que lo realiza (+2 PE).")
        if req.victim_player_id is not None:
            victim = session.get(Player, req.victim_player_id)
            if victim is None:
                raise NotFoundError("El jugador lesionado no existe.")
            if victim.team_id != _other_team_id(match, req.team_id):
                raise LeagueError("El jugador lesionado debe pertenecer al equipo rival.")
        if req.casualty_result is None and req.victim_player_id is not None:
            raise LeagueError("Indica el resultado de la tirada de heridas.")

    elif req.event_type == EventType.INJURY:
        # Lesion sin PE: el jugador indicado es el que resulta herido.
        if player is None:
            raise LeagueError("Indica el jugador lesionado.")
        if req.casualty_result is None:
            raise LeagueError("Indica el resultado de la tirada de heridas.")
        victim = player

    spp = spp_for_event(req.event_type, player=player, is_block_casualty=is_block)

    if req.event_type == EventType.INJURY:
        victim_id = player.id if player is not None else None
    elif req.event_type == EventType.CAS:
        victim_id = victim.id if victim is not None else req.victim_player_id
    else:
        victim_id = req.victim_player_id

    event = MatchEvent(
        match_id=match.id,
        team_id=req.team_id,
        player_id=req.player_id,
        event_type=req.event_type,
        turn=req.turn,
        spp_awarded=spp,
        is_block_casualty=is_block if req.event_type == EventType.CAS else False,
        victim_player_id=victim_id,
        casualty_result=req.casualty_result,
        note=req.note or "",
    )
    session.add(event)

    if player is not None and spp:
        award_spp(player, spp)
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
            revoke_spp(player, event.spp_awarded)
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

    if req.conceded_by_team_id is not None:
        require_participant(match, req.conceded_by_team_id)

    dice = rng or random.Random()

    # 1. MVP (obligatorio). Auto = 1 entre top 3; pick = el rival elige entre esos 3.
    # Quien concede no cobra el suyo: el rival se lleva los 8 SPP.
    _resolve_and_award_mvps(session, match, home, away, req, dice)

    # 2. Ganancias segun hinchas, tope de tesoreria y fluctuacion de aficion.
    home_economy, away_economy = league_engine.process_post_match_economy(
        session,
        match,
        home,
        away,
        home_winnings_roll=req.home_winnings_roll,
        away_winnings_roll=req.away_winnings_roll,
        home_fans_roll=req.home_fans_roll,
        away_fans_roll=req.away_fans_roll,
        conceded_by_team_id=req.conceded_by_team_id,
        rng=rng,
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

    cas_events = [
        e
        for e in session.exec(
            select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.id)
        ).all()
        if e.event_type in (EventType.CAS, EventType.INJURY)
    ]

    for event in cas_events:
        injured_id = event.victim_player_id
        if event.event_type == EventType.INJURY and injured_id is None:
            injured_id = event.player_id
        if injured_id is None or event.casualty_result is None:
            continue
        victim = session.get(Player, injured_id)
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

        # La Red de Seguridad solo cubre la muerte: ahi no hay decision y se
        # devuelve el valor actual (coste mas mejoras). Una lesion de por vida
        # no paga sola; si el entrenador despide al jugador, recupera el coste base.
        if mercy_active and result == CasualtyResult.DEAD:
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

    spills = league_engine.record_treasury_spills(session, match, home_economy, away_economy)
    tavern = [spill.headline for spill in spills]
    league_engine.write_match_chronicle(
        session,
        match,
        home,
        away,
        home_economy=home_economy,
        away_economy=away_economy,
        spills=spills,
        payouts=payouts,
        bounty=bounty_payout,
    )

    match.status = MatchStatus.COMPLETED
    match.completed_at = utcnow()
    session.add_all([match, home, away])
    session.commit()

    assignments = _after_match_completed(session, match)

    return MatchCompletionReport(
        match_id=match.id or 0,
        home_winnings=match.home_winnings,
        away_winnings=match.away_winnings,
        home_winnings_roll=home_economy.winnings_roll,
        away_winnings_roll=away_economy.winnings_roll,
        home_discarded=home_economy.discarded,
        away_discarded=away_economy.discarded,
        home_fans_before=home_economy.fans_before,
        home_fans_after=home_economy.fans_after,
        home_fans_roll=home_economy.fans_roll,
        away_fans_before=away_economy.fans_before,
        away_fans_after=away_economy.fans_after,
        away_fans_roll=away_economy.fans_roll,
        home_winner_bonus=home_economy.winner_bonus,
        away_winner_bonus=away_economy.winner_bonus,
        conceded_by_team_id=req.conceded_by_team_id,
        tavern=tavern,
        injuries=injuries,
        rookie_safety_payouts=payouts,
        bounty_payout=bounty_payout,
        recovered_players=recovered,
        sponsors=assignments,
    )


def _resolve_and_award_mvps(
    session: Session,
    match: Match,
    home: Team,
    away: Team,
    req: CompleteMatchRequest,
    rng: random.Random,
) -> None:
    """Resuelve MVP (auto o pick entre top 3) y otorga PE. Concesion: el rival cobra x2."""
    mvp_spp = rules.spp_for("MVP")
    conceded = req.conceded_by_team_id

    sides: list[tuple[Team, str, Optional[int], str, int]] = []
    if conceded == home.id:
        sides.append((away, req.away_mvp_mode, req.away_mvp_player_id, "away_mvp_player_id", mvp_spp * 2))
    elif conceded == away.id:
        sides.append((home, req.home_mvp_mode, req.home_mvp_player_id, "home_mvp_player_id", mvp_spp * 2))
    else:
        sides.append((home, req.home_mvp_mode, req.home_mvp_player_id, "home_mvp_player_id", mvp_spp))
        sides.append((away, req.away_mvp_mode, req.away_mvp_player_id, "away_mvp_player_id", mvp_spp))

    for team, mode, player_id, field, spp in sides:
        resolved_id = pick_mvp_player_id(
            session, match, team, mode=mode, player_id=player_id, rng=rng
        )
        player = session.get(Player, resolved_id)
        if player is None or player.team_id != team.id:
            raise LeagueError(f"El MVP indicado no pertenece a {team.name}.")
        award_spp(player, spp)
        session.add(player)
        setattr(match, field, resolved_id)
        note = "MVP del partido" if spp == mvp_spp else "MVP del partido y el del rival, que concedio"
        session.add(
            MatchEvent(
                match_id=match.id,
                team_id=team.id,
                player_id=resolved_id,
                event_type=EventType.MVP,
                spp_awarded=spp,
                note=note,
            )
        )


def _after_match_completed(session: Session, match: Match):
    """Avanza la jornada si procede, reevalua los patrocinadores y los anota."""
    state = league_engine.get_league_state(session)
    round_matches = session.exec(
        select(Match).where(Match.round_number == state.current_round)
    ).all()
    finished_round = None
    if round_matches and all(m.status == MatchStatus.COMPLETED for m in round_matches):
        finished_round = state.current_round
        if state.current_round < state.total_rounds:
            state.current_round += 1
            session.add(state)
            session.commit()

    assignments = league_engine.assign_sponsors(session, apply=True)
    if finished_round is not None:
        league_engine.write_sponsor_chronicle(session, finished_round, assignments)
        session.commit()
    return assignments


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
