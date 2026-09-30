"""Transiciones de partido y ajustes del comisario.

La interfaz no decide reglas: si el estado no cuadra, aquí sale un error claro.
"""

from __future__ import annotations

import json
import random

from sqlmodel import Session, select

from app.auth import RuleError, check_pin
from app.league_engine import (
    EVENT_TYPES,
    PLAYER_STATUSES,
    SPONSOR_IDS,
    VALID_STATUSES,
    assign_sponsors,
    bounty_profile,
    bounty_reward,
    build_standings,
    calculate_ctv,
    inducement_catalog,
    load_rules,
    mercy_applies,
    mercy_gold,
    spp_for,
)
from app.models import (
    LeagueState,
    Match,
    MatchEvent,
    MatchInducement,
    Player,
    PlayerInjury,
    Team,
)
from app.presenters import build_match_state


def ensure_state(session: Session) -> LeagueState:
    state = session.exec(select(LeagueState)).first()
    if state is None:
        state = LeagueState()
        session.add(state)
        session.flush()
    return state


def get_match(session: Session, match_id: int) -> Match:
    match = session.get(Match, match_id)
    if match is None:
        raise RuleError("Partido no encontrado.", 404)
    return match


def assert_participant(match: Match, team: Team) -> None:
    if team.id not in (match.home_team_id, match.away_team_id):
        raise RuleError("No juegas este partido.", 403)


def _players_of(session: Session, team_id: int) -> list[Player]:
    return list(session.exec(select(Player).where(Player.team_id == team_id)).all())


def _state_of(session: Session, match: Match) -> dict:
    session.flush()
    fresh = session.get(Match, match.id)
    return build_match_state(session, fresh)


def confirm_ready(session: Session, match: Match, team_id: int, pin: str) -> dict:
    if match.status not in ("SCHEDULED", "READY_CHECK"):
        raise RuleError("La comprobación de presencia solo está disponible antes del prepartido.")
    team = session.get(Team, team_id)
    if team is None or team.id not in (match.home_team_id, match.away_team_id):
        raise RuleError("Ese equipo no juega este partido.")
    check_pin(team, pin)
    if team.id == match.home_team_id:
        match.home_ready = True
    else:
        match.away_ready = True
    if match.status == "SCHEDULED":
        match.status = "READY_CHECK"
    if match.home_ready and match.away_ready:
        _snapshot_prematch(session, match)
        match.status = "PRE_MATCH"
    session.add(match)
    session.commit()
    return _state_of(session, match)


def _snapshot_prematch(session: Session, match: Match) -> None:
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:
        raise RuleError("Falta un equipo de este partido.")
    home_ctv = calculate_ctv(home, _players_of(session, home.id))["total"]
    away_ctv = calculate_ctv(away, _players_of(session, away.id))["total"]
    match.home_ctv = home_ctv
    match.away_ctv = away_ctv
    if home_ctv == away_ctv:
        match.petty_cash_team_id = None
        match.petty_cash_amount = 0
    elif home_ctv < away_ctv:
        match.petty_cash_team_id = home.id
        match.petty_cash_amount = away_ctv - home_ctv
    else:
        match.petty_cash_team_id = away.id
        match.petty_cash_amount = home_ctv - away_ctv
    state = ensure_state(session)
    if not match.bounty_id:
        match.bounty_id = state.active_bounty_id


def set_inducements(session: Session, match: Match, team_id: int, items: list) -> dict:
    if match.status != "PRE_MATCH":
        raise RuleError("Los incentivos solo se compran en el prepartido.")
    if match.petty_cash_team_id is None or team_id != match.petty_cash_team_id:
        raise RuleError(
            "Solo el equipo con menor valoración puede gastar el fondo menor, y únicamente esa diferencia."
        )
    catalog = {item["id"]: item for item in inducement_catalog()}
    cleaned: dict[str, int] = {}
    for item in items:
        if item.qty == 0:
            continue
        spec = catalog.get(item.id)
        if spec is None:
            raise RuleError(f"Incentivo desconocido: {item.id}.")
        if item.qty > spec["max"]:
            raise RuleError(f"{spec['name']} admite como máximo {spec['max']}.")
        cleaned[item.id] = cleaned.get(item.id, 0) + item.qty
        if cleaned[item.id] > spec["max"]:
            raise RuleError(f"{spec['name']} admite como máximo {spec['max']}.")
    total = sum(catalog[key]["cost"] * qty for key, qty in cleaned.items())
    if total > match.petty_cash_amount:
        raise RuleError("El fondo menor no llega. No puedes usar la tesorería para completar la compra.")
    existing = list(session.exec(select(MatchInducement).where(MatchInducement.match_id == match.id)).all())
    for row in existing:
        session.delete(row)
    session.flush()
    for inducement_id, qty in cleaned.items():
        session.add(
            MatchInducement(
                match_id=match.id,
                team_id=team_id,
                inducement_id=inducement_id,
                quantity=qty,
                unit_cost=catalog[inducement_id]["cost"],
            )
        )
    session.commit()
    return _state_of(session, match)


def _assign_roll(manual: int | None, digital: bool, low: int, high: int, label: str) -> int | None:
    if digital and manual is not None:
        raise RuleError(f"En {label} elige tirada digital o resultado manual, no las dos cosas.")
    if digital:
        if low == 1 and high == 16:
            return random.randint(1, 16)
        return random.randint(1, 6) + random.randint(1, 6)
    if manual is None:
        return None
    if manual < low or manual > high:
        raise RuleError(f"{label} tiene que estar entre {low} y {high}.")
    return manual


def apply_rolls(session: Session, match: Match, payload) -> dict:
    if match.status != "PRE_MATCH":
        raise RuleError("Las tiradas de prepartido solo se hacen antes de empezar el partido.")
    weather = _assign_roll(payload.weather_manual, payload.weather, 2, 12, "El clima")
    prayer = _assign_roll(payload.prayer_manual, payload.prayer, 1, 16, "Las plegarias")
    kickoff = _assign_roll(payload.kickoff_manual, payload.kickoff, 2, 12, "La patada inicial")
    if weather is not None:
        match.weather_roll = weather
    if prayer is not None:
        match.prayer_roll = prayer
    if kickoff is not None:
        match.kick_off_roll = kickoff
    if payload.kicking_team_id is not None:
        if payload.kicking_team_id not in (match.home_team_id, match.away_team_id):
            raise RuleError("Quien saca tiene que ser uno de los dos equipos.")
        match.kicking_team_id = payload.kicking_team_id
    session.add(match)
    session.commit()
    return _state_of(session, match)


def begin_match(session: Session, match: Match) -> dict:
    if match.status != "PRE_MATCH":
        raise RuleError("El partido solo puede empezar desde el prepartido.")
    missing = []
    if match.weather_roll is None:
        missing.append("clima")
    if match.prayer_roll is None:
        missing.append("plegarias")
    if match.kick_off_roll is None:
        missing.append("patada inicial")
    if match.kicking_team_id is None:
        missing.append("quién saca")
    if missing:
        raise RuleError("Falta registrar: " + ", ".join(missing) + ".")
    match.status = "IN_PROGRESS"
    session.add(match)
    session.commit()
    return _state_of(session, match)


def set_turn(session: Session, match: Match, turn: int) -> dict:
    if match.status != "IN_PROGRESS":
        raise RuleError("El turno solo se mueve con el partido en juego.")
    match.current_turn = turn
    session.add(match)
    session.commit()
    return _state_of(session, match)


def add_event(session: Session, match: Match, team_id: int, player_id: int, event_type: str, turn: int | None) -> dict:
    if match.status != "IN_PROGRESS":
        raise RuleError("Los eventos solo se registran con el partido en juego.")
    if team_id not in (match.home_team_id, match.away_team_id):
        raise RuleError("Ese equipo no juega este partido.")
    if event_type not in EVENT_TYPES or event_type == "MVP":
        raise RuleError("Ese evento no se anota desde el marcador en vivo.")
    player = session.get(Player, player_id)
    if player is None or player.team_id != team_id:
        raise RuleError("Ese jugador no está en la plantilla de ese equipo.")
    if player.status != "ACTIVE":
        raise RuleError(f"{player.name} no puede actuar ahora mismo ({player.status}).")
    resolved_turn = match.current_turn if turn is None else turn
    if resolved_turn < 0 or resolved_turn > 16:
        raise RuleError("El turno tiene que estar entre 0 y 16.")
    awarded = spp_for(event_type)
    session.add(
        MatchEvent(
            match_id=match.id,
            team_id=team_id,
            player_id=player.id,
            event_type=event_type,
            turn=resolved_turn,
            spp_awarded=awarded,
        )
    )
    player.spp += awarded
    if event_type == "TD":
        if team_id == match.home_team_id:
            match.home_td += 1
        else:
            match.away_td += 1
    match.current_turn = resolved_turn
    session.commit()
    return _state_of(session, match)


def reverse_event(session: Session, match: Match, event: MatchEvent) -> None:
    if event.player_id:
        player = session.get(Player, event.player_id)
        if player is not None:
            player.spp = max(0, player.spp - event.spp_awarded)
    if event.event_type == "TD":
        if event.team_id == match.home_team_id:
            match.home_td = max(0, match.home_td - 1)
        elif event.team_id == match.away_team_id:
            match.away_td = max(0, match.away_td - 1)


def undo_last_event(session: Session, match: Match) -> dict:
    if match.status != "IN_PROGRESS":
        raise RuleError("Solo se puede deshacer el último evento con el partido en juego.")
    event = session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.id.desc())
    ).first()
    if event is None:
        raise RuleError("No hay eventos que deshacer.")
    reverse_event(session, match, event)
    session.delete(event)
    session.commit()
    return _state_of(session, match)


def delete_event(session: Session, event_id: int) -> dict:
    event = session.get(MatchEvent, event_id)
    if event is None:
        raise RuleError("Evento no encontrado.", 404)
    match = get_match(session, event.match_id)
    reverse_event(session, match, event)
    session.delete(event)
    session.commit()
    return _state_of(session, match)


def use_benefit(session: Session, match: Match, team_id: int, benefit: str) -> dict:
    if match.status not in ("PRE_MATCH", "IN_PROGRESS"):
        raise RuleError("Ese beneficio solo se marca durante el prepartido o el partido.")
    if team_id not in (match.home_team_id, match.away_team_id):
        raise RuleError("Ese equipo no juega este partido.")
    team = session.get(Team, team_id)
    if team is None:
        raise RuleError("Equipo no encontrado.", 404)
    side = "home" if team_id == match.home_team_id else "away"
    if benefit == "reroll":
        if team.current_sponsor_id != "tabernero":
            raise RuleError("Ese equipo no tiene la segunda oportunidad del Tabernero.")
        flag = f"{side}_free_reroll_used"
    elif benefit == "bribe":
        if team.current_sponsor_id != "sindicato":
            raise RuleError("Ese equipo no tiene el soborno del Sindicato.")
        flag = f"{side}_free_bribe_used"
    else:
        raise RuleError("Beneficio desconocido.")
    if getattr(match, flag):
        raise RuleError("Ese beneficio ya se ha usado en este partido.")
    setattr(match, flag, True)
    session.add(match)
    session.commit()
    return _state_of(session, match)


def _winnings(manual: int | None) -> tuple[int, int]:
    rules = load_rules()["winnings"]
    if manual is None:
        roll = random.randint(1, rules["die"])
    else:
        if manual < 1 or manual > rules["die"]:
            raise RuleError("La ganancia es una tirada de 1d6.")
        roll = manual
    return roll, roll * rules["multiplier"]


def _prior_mercy(session: Session, team_id: int) -> int:
    rounds = set(load_rules()["mercy"]["rounds"])
    rows = list(session.exec(select(PlayerInjury).where(PlayerInjury.team_id == team_id)).all())
    return sum(1 for row in rows if row.result in ("DEAD", "PERMANENT") and row.round_number in rounds)


def complete_match(session: Session, match: Match, payload) -> dict:
    if match.status != "IN_PROGRESS":
        raise RuleError("Solo se cierra un partido que está en juego.")
    if match.closure_applied:
        raise RuleError("Este acta ya está cerrada.")
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:
        raise RuleError("Falta un equipo de este partido.")
    roster = _players_of(session, home.id) + _players_of(session, away.id)
    by_id = {player.id: player for player in roster}

    def check_mvp(player_id: int, team_id: int) -> Player:
        player = by_id.get(player_id)
        if player is None or player.team_id != team_id:
            raise RuleError("El MVP tiene que ser un jugador de ese equipo.")
        if player.status != "ACTIVE":
            raise RuleError(f"{player.name} no puede ser MVP en ese estado.")
        return player

    home_mvp = check_mvp(payload.home_mvp_player_id, home.id)
    away_mvp = check_mvp(payload.away_mvp_player_id, away.id)
    seen: set[int] = set()
    for injury in payload.injuries:
        if injury.player_id not in by_id:
            raise RuleError("Hay una lesión de un jugador que no está en este partido.")
        if injury.result not in ("MNG", "DEAD", "PERMANENT"):
            raise RuleError("La lesión tiene que ser MNG, permanente o muerte.")
        if injury.player_id in seen:
            raise RuleError("Un jugador no puede llevar dos resultados de lesión en el mismo acta.")
        seen.add(injury.player_id)
        if by_id[injury.player_id].status == "DEAD":
            raise RuleError(f"{by_id[injury.player_id].name} ya estaba muerto.")

    for player in roster:
        if (
            player.status == "MNG"
            and player.mng_until_round is not None
            and player.mng_until_round <= match.round_number
            and player.id not in seen
        ):
            player.status = "ACTIVE"
            player.mng_until_round = None

    _, home_gold = _winnings(payload.home_winnings_d6)
    _, away_gold = _winnings(payload.away_winnings_d6)
    home.treasury += home_gold
    away.treasury += away_gold
    match.home_winnings = home_gold
    match.away_winnings = away_gold

    def grant_mvp(player: Player, team_id: int) -> None:
        awarded = spp_for("MVP")
        session.add(
            MatchEvent(
                match_id=match.id,
                team_id=team_id,
                player_id=player.id,
                event_type="MVP",
                turn=None,
                spp_awarded=awarded,
            )
        )
        player.spp += awarded

    grant_mvp(home_mvp, home.id)
    grant_mvp(away_mvp, away.id)
    match.home_mvp_player_id = home_mvp.id
    match.away_mvp_player_id = away_mvp.id

    mercy_counts = {home.id: _prior_mercy(session, home.id), away.id: _prior_mercy(session, away.id)}
    teams = {home.id: home, away.id: away}
    for injury in payload.injuries:
        player = by_id[injury.player_id]
        note = (injury.note or "").strip()[:200]
        payout = 0
        if injury.result in ("DEAD", "PERMANENT") and mercy_applies(match.round_number):
            payout = mercy_gold(player.current_value, mercy_counts[player.team_id])
            mercy_counts[player.team_id] += 1
            teams[player.team_id].treasury += payout
        if injury.result == "DEAD":
            player.status = "DEAD"
            player.mng_until_round = None
        elif injury.result == "MNG":
            player.status = "MNG"
            player.mng_until_round = match.round_number + 1
        else:
            player.status = "ACTIVE"
            player.mng_until_round = None
        if note:
            player.injuries = f"{player.injuries} | {note}" if player.injuries else note
        session.add(
            PlayerInjury(
                match_id=match.id,
                team_id=player.team_id,
                player_id=player.id,
                round_number=match.round_number,
                result=injury.result,
                value_at_time=player.current_value,
                mercy_gold=payout,
                note=note,
            )
        )

    events = list(session.exec(select(MatchEvent).where(MatchEvent.match_id == match.id)).all())

    def count(team_id: int, kind: str) -> int:
        return sum(1 for event in events if event.team_id == team_id and event.event_type == kind)

    rules = load_rules()
    for team, td, conceded, sponsor_field, bounty_field in (
        (home, match.home_td, match.away_td, "home_sponsor_gold", "home_bounty_gold"),
        (away, match.away_td, match.home_td, "away_sponsor_gold", "away_bounty_gold"),
    ):
        caused = count(team.id, "CAS")
        if team.current_sponsor_id == "carniceria" and caused >= rules["carniceria_threshold"]:
            bonus = rules["carniceria_bonus"]
            team.treasury += bonus
            setattr(match, sponsor_field, bonus)
        reward = bounty_reward(
            match.bounty_id,
            td=td,
            cas=caused,
            fouls=count(team.id, "FOUL"),
            td_against=conceded,
        )
        if reward:
            team.treasury += reward
            setattr(match, bounty_field, reward)

    match.status = "COMPLETED"
    match.closure_applied = True
    maybe_advance_round(session)
    session.commit()
    return _state_of(session, match)


def maybe_advance_round(session: Session) -> None:
    state = ensure_state(session)
    current = state.current_round
    matches = list(session.exec(select(Match).where(Match.round_number == current)).all())
    if not matches or any(match.status != "COMPLETED" for match in matches):
        return
    if current >= 3:
        apply_sponsor_assignment(session)
    all_matches = list(session.exec(select(Match)).all())
    if not all_matches:
        return
    peak = max(match.round_number for match in all_matches)
    if current < peak:
        state.current_round = current + 1
        session.add(state)


def apply_sponsor_assignment(session: Session, choices: dict | None = None, override: dict | None = None) -> tuple[dict, list[str]]:
    teams = list(session.exec(select(Team)).all())
    matches = list(session.exec(select(Match)).all())
    events = list(session.exec(select(MatchEvent)).all())
    rows = build_standings(teams, matches, events)
    known = {team.id for team in teams}
    if override is not None:
        assignment: dict[str, int] = {}
        seen: set[int] = set()
        for sponsor, team_id in override.items():
            if sponsor not in SPONSOR_IDS:
                raise RuleError("Patrocinador desconocido.")
            try:
                numeric_id = int(team_id)
            except (TypeError, ValueError) as exc:
                raise RuleError("El equipo del patrocinio no es válido.") from exc
            if numeric_id not in known:
                raise RuleError("Hay un patrocinio asignado a un equipo que no existe.")
            if numeric_id in seen:
                raise RuleError("Un equipo no puede llevar dos patrocinadores.")
            seen.add(numeric_id)
            assignment[sponsor] = numeric_id
        log = ["Asignación manual del comisario."]
    else:
        manual = {}
        for key, value in (choices or {}).items():
            manual[int(key)] = value
        assignment, log = assign_sponsors(rows, manual=manual)
    for team in teams:
        team.current_sponsor_id = None
        session.add(team)
    by_id = {team.id: team for team in teams}
    for sponsor, team_id in assignment.items():
        by_id[team_id].current_sponsor_id = sponsor
    state = ensure_state(session)
    state.sponsor_log = json.dumps(log, ensure_ascii=False)
    session.add(state)
    return assignment, log


def recalculate(session: Session, choices: dict | None, override: dict | None) -> dict:
    assignment, log = apply_sponsor_assignment(session, choices=choices, override=override)
    session.commit()
    teams = list(session.exec(select(Team)).all())
    matches = list(session.exec(select(Match)).all())
    events = list(session.exec(select(MatchEvent)).all())
    return {
        "assignment": {sponsor: team_id for sponsor, team_id in assignment.items()},
        "log": log,
        "standings": build_standings(teams, matches, events),
    }


def update_player(session: Session, actor: Team, player_id: int, payload) -> dict:
    player = session.get(Player, player_id)
    if player is None:
        raise RuleError("Jugador no encontrado.", 404)
    if player.team_id != actor.id:
        raise RuleError("Solo puedes editar a los jugadores de tu equipo.", 403)

    def bounded(value: int | None, low: int, high: int, label: str) -> None:
        if value is None:
            return
        if value < low or value > high:
            raise RuleError(f"{label} tiene que estar entre {low} y {high}.")

    if payload.name is not None:
        name = payload.name.strip()
        if not name or len(name) > 40:
            raise RuleError("El nombre tiene que tener entre 1 y 40 caracteres.")
        player.name = name
    if payload.skills is not None:
        if len(payload.skills) > 300:
            raise RuleError("La lista de habilidades es demasiado larga.")
        player.skills = payload.skills.strip()
    if payload.injuries is not None:
        if len(payload.injuries) > 300:
            raise RuleError("El texto de lesiones es demasiado largo.")
        player.injuries = payload.injuries.strip()
    bounded(payload.current_value, 0, 500_000, "El valor")
    bounded(payload.ma, 1, 12, "El movimiento")
    bounded(payload.st, 1, 8, "La fuerza")
    bounded(payload.ag, 1, 6, "La agilidad")
    bounded(payload.pa, 1, 6, "El pase")
    bounded(payload.av, 3, 12, "La armadura")
    if payload.current_value is not None:
        player.current_value = payload.current_value
    if payload.ma is not None:
        player.ma = payload.ma
    if payload.st is not None:
        player.st = payload.st
    if payload.ag is not None:
        player.ag = payload.ag
    if payload.clear_pa:
        player.pa = None
    elif payload.pa is not None:
        player.pa = payload.pa
    if payload.av is not None:
        player.av = payload.av
    session.add(player)
    session.commit()
    session.refresh(player)
    from app.presenters import public_player

    return public_player(player)


def force_status(session: Session, match: Match, status: str) -> dict:
    if status not in VALID_STATUSES:
        raise RuleError("Estado de partido desconocido.")
    match.status = status
    if status == "SCHEDULED":
        match.home_ready = False
        match.away_ready = False
    session.add(match)
    if status == "COMPLETED":
        maybe_advance_round(session)
    session.commit()
    return _state_of(session, match)


def set_score(session: Session, match: Match, home_td: int, away_td: int) -> dict:
    match.home_td = home_td
    match.away_td = away_td
    session.add(match)
    session.commit()
    return _state_of(session, match)


def add_treasury(session: Session, team: Team, delta: int) -> dict:
    updated = team.treasury + delta
    if updated < 0:
        raise RuleError("La tesorería no puede quedar en negativo.")
    team.treasury = updated
    session.add(team)
    session.commit()
    session.refresh(team)
    from app.presenters import public_team

    return public_team(team, include_pin=True)


def set_player_status(session: Session, player: Player, status: str) -> dict:
    if status not in PLAYER_STATUSES:
        raise RuleError("Estado de jugador desconocido.")
    player.status = status
    if status == "ACTIVE":
        player.mng_until_round = None
    elif status == "MNG":
        state = ensure_state(session)
        player.mng_until_round = state.current_round + 1
    else:
        player.mng_until_round = None
    session.add(player)
    session.commit()
    session.refresh(player)
    from app.presenters import public_player

    return public_player(player)


def set_pin(session: Session, team: Team, pin: str) -> dict:
    if not (len(pin) == 4 and pin.isdigit()):
        raise RuleError("El PIN tiene que ser de 4 dígitos.")
    team.pin = pin
    session.add(team)
    session.commit()
    from app.presenters import public_team

    return public_team(team, include_pin=True)


def set_round(session: Session, round_number: int) -> dict:
    if round_number < 1 or round_number > 30:
        raise RuleError("La jornada tiene que estar entre 1 y 30.")
    state = ensure_state(session)
    state.current_round = round_number
    session.add(state)
    session.commit()
    return league_snapshot(session)


def set_bounty(session: Session, bounty_id: str | None) -> dict:
    if bounty_id is not None and bounty_profile(bounty_id) is None:
        raise RuleError("Esa recompensa semanal no existe.")
    state = ensure_state(session)
    state.active_bounty_id = bounty_id
    session.add(state)
    session.commit()
    session.refresh(state)
    return {"current_round": state.current_round, "active_bounty": bounty_profile(state.active_bounty_id), "sponsor_log": _log(state)}


def _log(state: LeagueState) -> list[str]:
    if not state.sponsor_log:
        return []
    try:
        parsed = json.loads(state.sponsor_log)
    except json.JSONDecodeError:
        return [state.sponsor_log]
    return parsed if isinstance(parsed, list) else [str(parsed)]


def league_snapshot(session: Session) -> dict:
    from app.presenters import public_team

    state = ensure_state(session)
    teams = list(session.exec(select(Team)).all())
    matches = list(session.exec(select(Match)).all())
    events = list(session.exec(select(MatchEvent)).all())
    return {
        "current_round": state.current_round,
        "active_bounty": bounty_profile(state.active_bounty_id),
        "sponsor_log": _log(state),
        "standings": build_standings(teams, matches, events),
        "teams": [public_team(team) for team in teams],
    }
