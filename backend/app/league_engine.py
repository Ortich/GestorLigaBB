"""FASE 2 - Motor de liga.

Contiene toda la logica de negocio de Blood Bowl que NO depende de HTTP:

* Calculo de la VAE/CTV y del Fondo Menor (Petty Cash).
* Tabla de clasificacion con el sistema de puntos y los desempates.
* Reasignacion de los 4 patrocinadores dinamicos (mecanica de catch-up).
* Red de Seguridad de Novatos (Mercy Rule).
* Recalculo integral de la liga a partir del historial de eventos.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Iterable, Optional

from sqlmodel import Session, select

from app import rules
from app.models import (
    Bounty,
    EventType,
    LeagueState,
    Match,
    MatchEvent,
    MatchStatus,
    Player,
    PlayerStatus,
    Sponsor,
    Team,
)
from app.schemas import CtvBreakdown, SponsorAssignment, StandingRow

#: Estados que consumen jugadores del roster pero no cuentan para la VAE.
CTV_EXCLUDED_STATUSES = {PlayerStatus.MNG, PlayerStatus.DEAD, PlayerStatus.RETIRED}


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #
def roll_dice(sides: int, count: int = 1, rng: Optional[random.Random] = None) -> int:
    generator = rng or random
    return sum(generator.randint(1, sides) for _ in range(count))


def roll_2d6(rng: Optional[random.Random] = None) -> int:
    return roll_dice(6, 2, rng)


def roll_d16(rng: Optional[random.Random] = None) -> int:
    return roll_dice(16, 1, rng)


def roll_d6(rng: Optional[random.Random] = None) -> int:
    return roll_dice(6, 1, rng)


# --------------------------------------------------------------------------- #
# VAE / CTV
# --------------------------------------------------------------------------- #
def player_counts_towards_ctv(player: Player) -> bool:
    return player.status not in CTV_EXCLUDED_STATUSES


def compute_ctv(session: Session, team: Team, players: Optional[Iterable[Player]] = None) -> CtvBreakdown:
    """Valoracion Actual de Equipo.

    Suma jugadores ACTIVOS + segundas oportunidades + ayudantes + animadoras +
    apotecario. La tesoreria y los hinchas dedicados NO suman.
    """
    if players is None:
        players = session.exec(select(Player).where(Player.team_id == team.id)).all()
    players = list(players)

    active = [p for p in players if player_counts_towards_ctv(p)]
    costs = rules.ctv_costs()

    players_value = sum(p.current_value for p in active)
    rerolls_value = team.rerolls * team.reroll_cost
    coaches_value = team.assistant_coaches * costs["assistant_coach"]
    cheer_value = team.cheerleaders * costs["cheerleader"]
    apo_value = costs["apothecary"] if team.apothecary else 0

    return CtvBreakdown(
        team_id=team.id or 0,
        players=players_value,
        rerolls=rerolls_value,
        assistant_coaches=coaches_value,
        cheerleaders=cheer_value,
        apothecary=apo_value,
        total=players_value + rerolls_value + coaches_value + cheer_value + apo_value,
        excluded_players=len(players) - len(active),
    )


def petty_cash_for(home_ctv: int, away_ctv: int, home_team_id: int, away_team_id: int) -> tuple[int, Optional[int]]:
    """Devuelve (importe, id del equipo beneficiado).

    El equipo con MENOR VAE recibe exactamente la diferencia. Si hay empate,
    nadie recibe Fondo Menor.
    """
    if home_ctv == away_ctv:
        return 0, None
    if home_ctv < away_ctv:
        return away_ctv - home_ctv, home_team_id
    return home_ctv - away_ctv, away_team_id


# --------------------------------------------------------------------------- #
# Clasificacion
# --------------------------------------------------------------------------- #
def _blank_row(team: Team) -> dict[str, Any]:
    return {
        "team_id": team.id,
        "team_name": team.name,
        "logo": team.logo,
        "race": team.race,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "points": 0,
        "td_for": 0,
        "td_against": 0,
        "cas_for": 0,
        "cas_against": 0,
        "fouls": 0,
        "passes": 0,
    }


def match_points(td_for: int, td_against: int, scoring: Optional[dict[str, Any]] = None) -> int:
    """Victoria 3, empate 1, derrota por 1 TD 1, derrota por mas de 1 TD 0."""
    scoring = scoring or rules.scoring_config()
    margin = td_for - td_against
    if margin > 0:
        return int(scoring.get("win", 3))
    if margin == 0:
        return int(scoring.get("draw", 1))
    if abs(margin) <= int(scoring.get("narrow_loss_margin", 1)):
        return int(scoring.get("narrow_loss", 1))
    return int(scoring.get("loss", 0))


def collect_team_stats(session: Session) -> dict[int, dict[str, Any]]:
    """Agrega resultados y eventos de todos los partidos COMPLETADOS."""
    teams = session.exec(select(Team)).all()
    stats = {team.id: _blank_row(team) for team in teams}

    matches = session.exec(select(Match).where(Match.status == MatchStatus.COMPLETED)).all()
    completed_ids = {m.id for m in matches}
    scoring = rules.scoring_config()

    for match in matches:
        home = stats.get(match.home_team_id)
        away = stats.get(match.away_team_id)
        if home is None or away is None:
            continue

        home["played"] += 1
        away["played"] += 1
        home["td_for"] += match.home_td
        home["td_against"] += match.away_td
        away["td_for"] += match.away_td
        away["td_against"] += match.home_td
        home["points"] += match_points(match.home_td, match.away_td, scoring)
        away["points"] += match_points(match.away_td, match.home_td, scoring)

        if match.home_td > match.away_td:
            home["wins"] += 1
            away["losses"] += 1
        elif match.home_td < match.away_td:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1

    if completed_ids:
        events = session.exec(select(MatchEvent).where(MatchEvent.match_id.in_(completed_ids))).all()
        match_by_id = {m.id: m for m in matches}
        for event in events:
            row = stats.get(event.team_id)
            if row is None:
                continue
            if event.event_type == EventType.CAS:
                row["cas_for"] += 1
                match = match_by_id.get(event.match_id)
                if match is not None:
                    rival_id = match.away_team_id if event.team_id == match.home_team_id else match.home_team_id
                    if rival_id in stats:
                        stats[rival_id]["cas_against"] += 1
            elif event.event_type == EventType.FOUL:
                row["fouls"] += 1
            elif event.event_type == EventType.PASS:
                row["passes"] += 1

    for row in stats.values():
        row["td_diff"] = row["td_for"] - row["td_against"]
        row["cas_diff"] = row["cas_for"] - row["cas_against"]

    return stats


def compute_standings(session: Session) -> list[StandingRow]:
    """Tabla ordenada por puntos y los desempates: dif. TD, dif. bajas y TD a favor."""
    stats = collect_team_stats(session)
    teams = {t.id: t for t in session.exec(select(Team)).all()}
    sponsors = {s.id: s for s in session.exec(select(Sponsor)).all()}

    ordered = sorted(
        stats.values(),
        key=lambda r: (
            -r["points"],
            -r["td_diff"],
            -r["cas_diff"],
            -r["td_for"],
            r["team_name"].lower(),
        ),
    )

    rows: list[StandingRow] = []
    for position, row in enumerate(ordered, start=1):
        team = teams.get(row["team_id"])
        sponsor = sponsors.get(team.current_sponsor_id) if team and team.current_sponsor_id else None
        ctv = compute_ctv(session, team).total if team else 0
        rows.append(
            StandingRow(
                position=position,
                ctv=ctv,
                sponsor_code=sponsor.code if sponsor else None,
                sponsor_name=sponsor.name if sponsor else None,
                **row,
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Patrocinadores dinamicos
# --------------------------------------------------------------------------- #
_METRIC_LABEL = {
    "LAST_IN_TABLE": "Ultimo clasificado",
    "WORST_TD_DIFF": "Peor diferencia de TD",
    "MOST_CAS": "Mas bajas causadas",
    "MOST_FOULS": "Mas faltas cometidas",
}


def _metric_ranking(metric: str, standings: list[StandingRow]) -> list[tuple[int, float]]:
    """Ranking de candidatos (mejor candidato primero) para una metrica.

    Los empates se rompen dando prioridad al equipo peor clasificado, que es la
    logica de catch-up de la liga.
    """
    if metric == "LAST_IN_TABLE":
        ordered = sorted(standings, key=lambda r: -r.position)
        return [(r.team_id, float(r.position)) for r in ordered]
    if metric == "WORST_TD_DIFF":
        ordered = sorted(standings, key=lambda r: (r.td_diff, -r.position))
        return [(r.team_id, float(r.td_diff)) for r in ordered]
    if metric == "MOST_CAS":
        ordered = sorted(standings, key=lambda r: (-r.cas_for, -r.position))
        return [(r.team_id, float(r.cas_for)) for r in ordered]
    if metric == "MOST_FOULS":
        ordered = sorted(standings, key=lambda r: (-r.fouls, -r.position))
        return [(r.team_id, float(r.fouls)) for r in ordered]
    return []


def _preference_index(team: Optional[Team], sponsor_code: str, default_priority: dict[str, int]) -> int:
    """Orden de preferencia del equipo cuando lidera dos metricas a la vez."""
    if team and team.sponsor_preference:
        prefs = [c.strip() for c in team.sponsor_preference.split(",") if c.strip()]
        if sponsor_code in prefs:
            return prefs.index(sponsor_code)
    return 100 + default_priority.get(sponsor_code, 99)


def last_fully_completed_round(session: Session) -> int:
    matches = session.exec(select(Match)).all()
    if not matches:
        return 0
    by_round: dict[int, list[Match]] = defaultdict(list)
    for match in matches:
        by_round[match.round_number].append(match)

    last = 0
    for round_number in sorted(by_round):
        if all(m.status == MatchStatus.COMPLETED for m in by_round[round_number]):
            last = round_number
        else:
            break
    return last


def assign_sponsors(
    session: Session,
    *,
    apply: bool = True,
    force: bool = False,
    standings: Optional[list[StandingRow]] = None,
) -> list[SponsorAssignment]:
    """Reasigna los 4 patrocinadores dinamicos.

    Cada patrocinador va a un unico equipo. Si un equipo encabeza varias
    metricas se queda solo con una (segun su preferencia) y las demas pasan al
    siguiente del ranking. El equipo peor clasificado elige primero.
    """
    sponsors = session.exec(select(Sponsor).order_by(Sponsor.priority)).all()
    if not sponsors:
        return []

    standings = standings if standings is not None else compute_standings(session)
    if not standings:
        return []

    first_round = int(rules.sponsor_rules().get("first_round", 3))
    if not force and last_fully_completed_round(session) < first_round:
        return []

    teams = {t.id: t for t in session.exec(select(Team)).all()}
    position_by_team = {row.team_id: row.position for row in standings}
    default_priority = {s.code: s.priority for s in sponsors}

    rankings = {s.code: _metric_ranking(s.metric, standings) for s in sponsors}
    sponsor_by_code = {s.code: s for s in sponsors}

    pending = [s.code for s in sponsors]
    taken_teams: set[int] = set()
    result: dict[str, tuple[Optional[int], Optional[float]]] = {}

    while pending:
        candidates: dict[str, tuple[int, float]] = {}
        for code in list(pending):
            nxt = next(((tid, val) for tid, val in rankings[code] if tid not in taken_teams), None)
            if nxt is None:
                result[code] = (None, None)
                pending.remove(code)
                continue
            candidates[code] = nxt

        if not candidates:
            break

        by_team: dict[int, list[str]] = defaultdict(list)
        for code, (team_id, _value) in candidates.items():
            by_team[team_id].append(code)

        # El equipo mas bajo en la tabla elige primero.
        progressed = False
        for team_id in sorted(by_team, key=lambda t: -position_by_team.get(t, 0)):
            if team_id in taken_teams:
                continue
            codes = by_team[team_id]
            chosen = min(codes, key=lambda c: _preference_index(teams.get(team_id), c, default_priority))
            result[chosen] = (team_id, candidates[chosen][1])
            taken_teams.add(team_id)
            pending.remove(chosen)
            progressed = True

        if not progressed:
            break

    assignments: list[SponsorAssignment] = []
    for sponsor in sponsors:
        team_id, value = result.get(sponsor.code, (None, None))
        team = teams.get(team_id) if team_id else None
        assignments.append(
            SponsorAssignment(
                sponsor_code=sponsor.code,
                sponsor_name=sponsor.name,
                team_id=team_id,
                team_name=team.name if team else None,
                metric=sponsor.metric,
                metric_value=value,
                reason=f"{_METRIC_LABEL.get(sponsor.metric, sponsor.metric)}: {value:g}" if value is not None else "Sin candidato",
            )
        )

    if apply:
        for team in teams.values():
            team.current_sponsor_id = None
            session.add(team)
        for assignment in assignments:
            if assignment.team_id is None:
                continue
            team = teams[assignment.team_id]
            team.current_sponsor_id = sponsor_by_code[assignment.sponsor_code].id
            session.add(team)
        session.commit()

    return assignments


# --------------------------------------------------------------------------- #
# Red de Seguridad de Novatos (Mercy Rule)
# --------------------------------------------------------------------------- #
def rookie_safety_percentage(previous_claims: int) -> int:
    tiers = rules.rookie_safety_config().get("tiers", [100, 50, 25])
    index = min(previous_claims, len(tiers) - 1)
    return int(tiers[index])


def rookie_safety_payout(previous_claims: int, player_value: int) -> int:
    return player_value * rookie_safety_percentage(previous_claims) // 100


def rookie_safety_active(round_number: int, state: Optional[LeagueState] = None) -> bool:
    last_round = int(
        (state.rookie_safety_last_round if state else None)
        or rules.rookie_safety_config().get("last_round", 2)
    )
    return round_number <= last_round


# --------------------------------------------------------------------------- #
# Recalculo integral
# --------------------------------------------------------------------------- #
def recalculate_league(session: Session) -> dict[str, Any]:
    """Regenera marcadores, clasificacion y patrocinadores desde los eventos."""
    matches = session.exec(select(Match)).all()
    events = session.exec(select(MatchEvent)).all()

    td_by_match: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        if event.event_type == EventType.TD:
            td_by_match[event.match_id][event.team_id] += 1

    fixed: list[dict[str, Any]] = []
    for match in matches:
        if match.status not in (MatchStatus.IN_PROGRESS, MatchStatus.COMPLETED):
            continue
        tally = td_by_match.get(match.id, {})
        home_td = tally.get(match.home_team_id, 0)
        away_td = tally.get(match.away_team_id, 0)
        if (match.home_td, match.away_td) != (home_td, away_td):
            fixed.append(
                {
                    "match_id": match.id,
                    "before": f"{match.home_td}-{match.away_td}",
                    "after": f"{home_td}-{away_td}",
                }
            )
            match.home_td = home_td
            match.away_td = away_td
            session.add(match)
    session.commit()

    standings = compute_standings(session)
    assignments = assign_sponsors(session, apply=True, force=True, standings=standings)

    return {
        "matches_fixed": fixed,
        "standings": [row.model_dump() for row in compute_standings(session)],
        "sponsors": [a.model_dump() for a in assignments],
    }


# --------------------------------------------------------------------------- #
# Estado de liga
# --------------------------------------------------------------------------- #
def get_league_state(session: Session) -> LeagueState:
    state = session.get(LeagueState, 1)
    if state is None:
        state = LeagueState(id=1)
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def active_bounty(session: Session) -> Optional[Bounty]:
    state = get_league_state(session)
    if state.active_bounty_id is None:
        return None
    return session.get(Bounty, state.active_bounty_id)
