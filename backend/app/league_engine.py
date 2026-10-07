"""FASE 2 - Motor de liga.

Contiene toda la logica de negocio de Blood Bowl que NO depende de HTTP:

* Calculo de la VAE/CTV y del Fondo Menor (Petty Cash).
* Tabla de clasificacion con el sistema de puntos y los desempates.
* Reasignacion de los 4 patrocinadores dinamicos (mecanica de catch-up).
* Red de Seguridad de Novatos (Mercy Rule).
* Economia de cierre: ganancias segun hinchas, fluctuacion de aficion y tope de tesoreria.
* Recalculo integral de la liga a partir del historial de eventos.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from sqlmodel import Session, select

from app import rules
from app.errors import LeagueError
from app.models import (
    Bounty,
    CasualtyResult,
    ChronicleEntry,
    ChronicleKind,
    EventType,
    LeagueState,
    Match,
    MatchEvent,
    MatchStatus,
    Player,
    PlayerStatus,
    Sponsor,
    Team,
    TreasurySpill,
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
# Economia de cierre
# --------------------------------------------------------------------------- #
FAN_MIN = 1
FAN_MAX = 7
FAN_PURCHASE_MAX = 3
TREASURY_CAP = 150_000
WINNINGS_MULTIPLIER = 10_000
TAVERN_NOTE = "Tus jugadores se han gastado el exceso de oro en la taberna local"

# Resultado economico de un equipo: victoria, derrota, empate o concesion.
Outcome = str


@dataclass
class SideEconomy:
    """Oro y aficion de un equipo al cerrar el acta."""

    team_id: int
    team_name: str
    winnings_roll: int
    fans_used: int
    winner_bonus: int
    winnings: int
    discarded: int
    treasury: int
    fans_before: int
    fans_roll: Optional[int]
    fans_after: int
    conceded: bool
    message: str


def clamp_dedicated_fans(value: int) -> int:
    """Los hinchas dedicados viven siempre entre 1 y 7."""
    return max(FAN_MIN, min(FAN_MAX, int(value)))


def _require_d6(value: Optional[int], rng: Optional[random.Random], label: str) -> int:
    rolled = roll_d6(rng) if value is None else value
    if not 1 <= rolled <= 6:
        raise LeagueError(f"La tirada de ganancias del equipo {label} debe estar entre 1 y 6.")
    return rolled


def _require_2d6(value: Optional[int], rng: Optional[random.Random], label: str) -> int:
    rolled = roll_2d6(rng) if value is None else value
    if not 2 <= rolled <= 12:
        raise LeagueError(f"La tirada de hinchas del equipo {label} es 2D6 y debe estar entre 2 y 12.")
    return rolled


def match_outcomes(
    home_td: int,
    away_td: int,
    *,
    conceded_by: Optional[int],
    home_id: int,
    away_id: int,
) -> tuple[Outcome, Outcome]:
    """Quien gana, pierde o concede. La concesion manda sobre el marcador."""
    if conceded_by is not None and conceded_by not in (home_id, away_id):
        raise LeagueError("El equipo que concede no juega este partido.")
    if conceded_by == home_id:
        return "concede", "win"
    if conceded_by == away_id:
        return "win", "concede"
    if home_td > away_td:
        return "win", "loss"
    if away_td > home_td:
        return "loss", "win"
    return "draw", "draw"


def winnings_formula(d6: int, dedicated_fans: int, outcome: Outcome) -> tuple[int, int]:
    """Oro de la tirada y el bono de victoria (0 o 1).

    Ganador: ((1D6 + 1) + hinchas) × 10.000.
    Perdedor, empate o quien concede: (1D6 + hinchas) × 10.000.
    """
    bonus = 1 if outcome == "win" else 0
    return (d6 + bonus + dedicated_fans) * WINNINGS_MULTIPLIER, bonus


def next_dedicated_fans(current: int, outcome: Outcome, roll: Optional[int]) -> int:
    """Aficion de la jornada siguiente, ya recortada a 1–7.

    El 2D6 se compara con los hinchas de antes de actualizarlos.
    Quien concede pierde 1 sin tirar.
    """
    if outcome == "concede":
        return clamp_dedicated_fans(current - 1)
    if roll is None:
        raise LeagueError("Falta la tirada de hinchas.")
    if outcome == "win":
        delta = 1 if roll >= current else 0
    elif outcome == "loss":
        delta = -1 if roll <= current else 0
    elif roll > current:
        delta = 1
    elif roll < current:
        delta = -1
    else:
        delta = 0
    return clamp_dedicated_fans(current + delta)


def _fan_message(before: int, after: int) -> str:
    if after > before:
        return f"La aficion crece a {after}."
    if after < before:
        return f"La aficion baja a {after}."
    return f"La aficion se queda en {after}."


def _apply_side(
    team: Team,
    *,
    outcome: Outcome,
    d6: int,
    credit: int,
    fans_roll: Optional[int],
) -> SideEconomy:
    """Suma el oro, aplica el tope y despues mueve los hinchas."""
    fans_before = team.fans
    bonus = 1 if outcome == "win" else 0
    team.treasury += credit
    discarded = 0
    if team.treasury > TREASURY_CAP:
        discarded = team.treasury - TREASURY_CAP
        team.treasury = TREASURY_CAP

    if outcome == "concede":
        used_roll = None
    else:
        used_roll = fans_roll
    fans_after = next_dedicated_fans(fans_before, outcome, used_roll)
    team.fans = fans_after

    notes = []
    if discarded:
        notes.append(TAVERN_NOTE)
    notes.append(_fan_message(fans_before, fans_after))
    return SideEconomy(
        team_id=team.id or 0,
        team_name=team.name,
        winnings_roll=d6,
        fans_used=fans_before,
        winner_bonus=bonus,
        winnings=credit,
        discarded=discarded,
        treasury=team.treasury,
        fans_before=fans_before,
        fans_roll=used_roll,
        fans_after=fans_after,
        conceded=outcome == "concede",
        message=" ".join(notes),
    )


def format_gold(amount: int) -> str:
    """40.000 mo, con el punto de millares que usa el panfleto."""
    return f"{amount:,}".replace(",", ".") + " mo"


def tavern_headline(team_name: str, gold_lost: int, treasury_before: int) -> str:
    """Titular de la fiesta que se fue de madre. El oro perdido ya está en la cifra."""
    lost = format_gold(gold_lost)
    if treasury_before >= TREASURY_CAP:
        return (
            f"{team_name} está tan desfasado que la fiesta se les fue de madre: "
            f"se dejaron {lost} en la taberna."
        )
    return (
        f"En {team_name} la fiesta se les fue de las manos al llegar al tope: "
        f"se dejaron {lost} en la taberna."
    )


def record_treasury_spills(
    session: Session,
    match: Match,
    *sides: SideEconomy,
) -> list[TreasurySpill]:
    """Deja una fila por cada equipo que pierde oro en este partido.

    Si el acta se cierra otra vez, la fila anterior de ese partido se sustituye.
    """
    previous = session.exec(select(TreasurySpill).where(TreasurySpill.match_id == match.id)).all()
    for row in previous:
        session.delete(row)
    if previous:
        session.flush()

    created: list[TreasurySpill] = []
    for side in sides:
        if side.discarded <= 0:
            continue
        treasury_before = side.treasury + side.discarded - side.winnings
        spill = TreasurySpill(
            match_id=match.id or 0,
            team_id=side.team_id,
            round_number=match.round_number,
            gold_lost=side.discarded,
            winnings=side.winnings,
            treasury_before=treasury_before,
            headline=tavern_headline(side.team_name, side.discarded, treasury_before),
        )
        session.add(spill)
        created.append(spill)
    return created


# Hechos del partido que se reescriben al cerrar el acta. Fichajes y despidos no.
MATCH_CHRONICLE_KINDS = (
    ChronicleKind.RESULT,
    ChronicleKind.CONCESSION,
    ChronicleKind.TD,
    ChronicleKind.FOUL,
    ChronicleKind.INT,
    ChronicleKind.INJURY,
    ChronicleKind.DEATH,
    ChronicleKind.MERCY,
    ChronicleKind.MVP,
    ChronicleKind.BOUNTY,
    ChronicleKind.FANS,
    ChronicleKind.TAVERN,
)

_KIND_ORDER = {kind: index * 10 for index, kind in enumerate(ChronicleKind)}

_CASUALTY_EFFECT = {
    CasualtyResult.BADLY_HURT: "Sin secuelas",
    CasualtyResult.SERIOUSLY_HURT: "Se pierde el proximo partido",
    CasualtyResult.SERIOUS_INJURY: "Lesion persistente",
    CasualtyResult.LASTING_INJURY_MA: "-1 MA",
    CasualtyResult.LASTING_INJURY_ST: "-1 ST",
    CasualtyResult.LASTING_INJURY_AG: "-1 AG",
    CasualtyResult.LASTING_INJURY_PA: "-1 PA",
    CasualtyResult.LASTING_INJURY_AV: "-1 AV",
    CasualtyResult.DEAD: "Muerto",
}


def chronicle_round_for_team(session: Session, team_id: int) -> int:
    """Jornada a la que pertenece un fichaje o un despido.

    Es la del ultimo partido ya jugado por ese equipo: el cambio sale de esa semana.
    Si todavia no ha jugado, cae en la jornada en curso.
    """
    last = session.exec(
        select(Match)
        .where(Match.status == MatchStatus.COMPLETED)
        .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
        .order_by(Match.round_number.desc(), Match.id.desc())
    ).first()
    if last is not None:
        return last.round_number
    return get_league_state(session).current_round


def _chronicle(
    *,
    round_number: int,
    team_id: int,
    team_name: str,
    kind: ChronicleKind,
    headline: str,
    match_id: Optional[int] = None,
    player_id: Optional[int] = None,
    player_name: str = "",
    gold: Optional[int] = None,
) -> ChronicleEntry:
    return ChronicleEntry(
        round_number=round_number,
        match_id=match_id,
        team_id=team_id,
        team_name=team_name,
        player_id=player_id,
        player_name=player_name,
        kind=kind,
        headline=headline,
        gold=gold,
        sort_order=_KIND_ORDER[kind],
    )


def _replace_chronicle(
    session: Session,
    *,
    round_number: Optional[int] = None,
    match_id: Optional[int] = None,
    kinds: tuple[ChronicleKind, ...],
) -> None:
    query = select(ChronicleEntry).where(ChronicleEntry.kind.in_(kinds))  # type: ignore[attr-defined]
    if match_id is not None:
        query = query.where(ChronicleEntry.match_id == match_id)
    if round_number is not None:
        query = query.where(ChronicleEntry.round_number == round_number)
    previous = session.exec(query).all()
    for row in previous:
        session.delete(row)
    if previous:
        session.flush()


def dismissal_headline(team_name: str, player: Player) -> str:
    refund = format_gold(player.cost)
    if player.current_value != player.cost:
        return (
            f"{team_name} despide a {player.name} "
            f"(valía {format_gold(player.current_value)}) y recupera {refund} de coste base."
        )
    return f"{team_name} despide a {player.name} y recupera {refund}."


def record_dismissal(session: Session, team: Team, player: Player) -> ChronicleEntry:
    match_round = chronicle_round_for_team(session, team.id or 0)
    last = session.exec(
        select(Match)
        .where(Match.status == MatchStatus.COMPLETED)
        .where((Match.home_team_id == team.id) | (Match.away_team_id == team.id))
        .order_by(Match.round_number.desc(), Match.id.desc())
    ).first()
    entry = _chronicle(
        round_number=match_round,
        match_id=last.id if last is not None else None,
        team_id=team.id or 0,
        team_name=team.name,
        player_id=player.id,
        player_name=player.name,
        kind=ChronicleKind.DISMISSAL,
        headline=dismissal_headline(team.name, player),
        gold=player.cost,
    )
    session.add(entry)
    return entry


def record_signing(session: Session, team: Team, player: Player) -> ChronicleEntry:
    match_round = chronicle_round_for_team(session, team.id or 0)
    last = session.exec(
        select(Match)
        .where(Match.status == MatchStatus.COMPLETED)
        .where((Match.home_team_id == team.id) | (Match.away_team_id == team.id))
        .order_by(Match.round_number.desc(), Match.id.desc())
    ).first()
    entry = _chronicle(
        round_number=match_round,
        match_id=last.id if last is not None else None,
        team_id=team.id or 0,
        team_name=team.name,
        player_id=player.id,
        player_name=player.name,
        kind=ChronicleKind.SIGNING,
        headline=(
            f"{team.name} contrata a {player.name}, {player.position}, por {format_gold(player.cost)}."
        ),
        gold=player.cost,
    )
    session.add(entry)
    return entry


def write_sponsor_chronicle(
    session: Session, round_number: int, assignments: list[SponsorAssignment]
) -> list[ChronicleEntry]:
    """Foto de los patrocinadores al cerrar una jornada, desde la jornada 3."""
    first_round = int(rules.sponsor_rules().get("first_round", 3))
    if round_number < first_round:
        return []
    _replace_chronicle(session, round_number=round_number, kinds=(ChronicleKind.SPONSOR,))
    created: list[ChronicleEntry] = []
    for assignment in assignments:
        if assignment.team_id is None or not assignment.team_name:
            continue
        reason = f" ({assignment.reason})" if assignment.reason else ""
        entry = _chronicle(
            round_number=round_number,
            team_id=assignment.team_id,
            team_name=assignment.team_name,
            kind=ChronicleKind.SPONSOR,
            headline=f"{assignment.sponsor_name} se queda con {assignment.team_name}{reason}.",
        )
        session.add(entry)
        created.append(entry)
    return created


def write_match_chronicle(
    session: Session,
    match: Match,
    home: Team,
    away: Team,
    *,
    home_economy: SideEconomy,
    away_economy: SideEconomy,
    spills: list[TreasurySpill],
    payouts: list[dict[str, Any]],
    bounty: Optional[dict[str, Any]],
) -> list[ChronicleEntry]:
    """Sustituye el relato de este partido. Lo ya fichado o despedido no se toca."""
    if match.id is None:
        return []
    _replace_chronicle(session, match_id=match.id, kinds=MATCH_CHRONICLE_KINDS)

    teams = {home.id: home, away.id: away}
    events = session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.id)
    ).all()
    player_ids = {
        pid
        for event in events
        for pid in (event.player_id, event.victim_player_id)
        if pid is not None
    }
    player_ids.update(
        pid for pid in (match.home_mvp_player_id, match.away_mvp_player_id) if pid is not None
    )
    players = {
        player.id: player
        for player in (
            session.exec(select(Player).where(Player.id.in_(player_ids))).all()  # type: ignore[attr-defined]
            if player_ids
            else []
        )
    }

    created: list[ChronicleEntry] = []

    def add(entry: ChronicleEntry) -> None:
        session.add(entry)
        created.append(entry)

    add(
        _chronicle(
            round_number=match.round_number,
            match_id=match.id,
            team_id=home.id or 0,
            team_name=home.name,
            kind=ChronicleKind.RESULT,
            headline=f"{home.name} {match.home_td}–{match.away_td} {away.name}.",
        )
    )

    if match.conceded_by_team_id is not None:
        conceder = home if match.conceded_by_team_id == home.id else away
        rival = away if conceder is home else home
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=conceder.id or 0,
                team_name=conceder.name,
                kind=ChronicleKind.CONCESSION,
                headline=(
                    f"{conceder.name} concede contra {rival.name}. "
                    "Se van sin oro y pierden un hincha."
                ),
            )
        )

    for event in events:
        team = teams.get(event.team_id)
        if team is None or event.event_type not in (EventType.TD, EventType.FOUL, EventType.INT):
            continue
        player = players.get(event.player_id) if event.player_id else None
        player_name = player.name if player is not None else ""
        who = player_name or team.name
        if event.event_type == EventType.TD:
            headline = f"{who} anota para {team.name}."
            kind = ChronicleKind.TD
        elif event.event_type == EventType.FOUL:
            headline = f"{who} comete una falta con {team.name}."
            kind = ChronicleKind.FOUL
        else:
            headline = f"{who} intercepta un pase para {team.name}."
            kind = ChronicleKind.INT
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=team.id or 0,
                team_name=team.name,
                player_id=event.player_id,
                player_name=player_name,
                kind=kind,
                headline=headline,
            )
        )

    for event in events:
        if event.event_type not in (EventType.CAS, EventType.INJURY) or event.casualty_result is None:
            continue
        effect = _CASUALTY_EFFECT.get(event.casualty_result, "")
        if effect == "Sin secuelas":
            continue
        injured_id = event.victim_player_id or (
            event.player_id if event.event_type == EventType.INJURY else None
        )
        victim = players.get(injured_id) if injured_id else None
        if victim is None:
            continue
        victim_team = session.get(Team, victim.team_id)
        team_name = victim_team.name if victim_team is not None else ""
        kind = ChronicleKind.DEATH if event.casualty_result == CasualtyResult.DEAD else ChronicleKind.INJURY
        if kind == ChronicleKind.DEATH:
            headline = f"{victim.name} ({team_name}) muere en el campo."
        else:
            headline = f"{victim.name} ({team_name}) queda lesionado: {effect}."
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=victim.team_id,
                team_name=team_name,
                player_id=victim.id,
                player_name=victim.name,
                kind=kind,
                headline=headline,
            )
        )

    for payout in payouts:
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=payout["team_id"],
                team_name=payout["team_name"],
                player_name=payout.get("player_name", ""),
                kind=ChronicleKind.MERCY,
                headline=(
                    f"{payout['team_name']} cobra {format_gold(payout['gold'])} "
                    f"de la Red de Seguridad por la muerte de {payout['player_name']}."
                ),
                gold=payout["gold"],
            )
        )

    for team, player_id in (
        (home, match.home_mvp_player_id),
        (away, match.away_mvp_player_id),
    ):
        if player_id is None:
            continue
        player = players.get(player_id)
        player_name = player.name if player is not None else ""
        who = player_name or "Un jugador"
        extra = ""
        if match.conceded_by_team_id not in (None, team.id):
            extra = " Se lleva tambien el MVP del rival, que concedio."
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=team.id or 0,
                team_name=team.name,
                player_id=player_id,
                player_name=player_name,
                kind=ChronicleKind.MVP,
                headline=f"{who} es el MVP de {team.name}.{extra}",
            )
        )

    if bounty is not None:
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=bounty["team_id"],
                team_name=bounty["team_name"],
                kind=ChronicleKind.BOUNTY,
                headline=(
                    f"{bounty['team_name']} cumple {bounty['bounty']} "
                    f"y cobra {format_gold(bounty['gold'])}."
                ),
                gold=bounty["gold"],
            )
        )

    for side in (home_economy, away_economy):
        if side.fans_after == side.fans_before:
            continue
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=side.team_id,
                team_name=side.team_name,
                kind=ChronicleKind.FANS,
                headline=(
                    f"La afición de {side.team_name} pasa de {side.fans_before} a {side.fans_after}."
                ),
            )
        )

    names = {side.team_id: side.team_name for side in (home_economy, away_economy)}
    for spill in spills:
        add(
            _chronicle(
                round_number=match.round_number,
                match_id=match.id,
                team_id=spill.team_id,
                team_name=names.get(spill.team_id, ""),
                kind=ChronicleKind.TAVERN,
                headline=spill.headline,
                gold=spill.gold_lost,
            )
        )

    return created


def process_post_match_economy(
    session: Session,
    match: Match,
    home: Team,
    away: Team,
    *,
    home_winnings_roll: Optional[int] = None,
    away_winnings_roll: Optional[int] = None,
    home_fans_roll: Optional[int] = None,
    away_fans_roll: Optional[int] = None,
    conceded_by_team_id: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> tuple[SideEconomy, SideEconomy]:
    """Ganancias, tope de tesoreria y aficion de los dos equipos.

    El oro usa los hinchas de antes del partido. La aficion se mueve despues.
    No hace commit: el cierre del acta guarda los dos equipos juntos.
    """
    home_outcome, away_outcome = match_outcomes(
        match.home_td,
        match.away_td,
        conceded_by=conceded_by_team_id,
        home_id=home.id or 0,
        away_id=away.id or 0,
    )
    home_d6 = _require_d6(home_winnings_roll, rng, "local")
    away_d6 = _require_d6(away_winnings_roll, rng, "visitante")

    home_formula, _home_bonus = winnings_formula(home_d6, home.fans, home_outcome)
    away_formula, _away_bonus = winnings_formula(away_d6, away.fans, away_outcome)
    if home_outcome == "concede":
        home_credit, away_credit = 0, home_formula + away_formula
    elif away_outcome == "concede":
        home_credit, away_credit = home_formula + away_formula, 0
    else:
        home_credit, away_credit = home_formula, away_formula

    home_fans_die = None if home_outcome == "concede" else _require_2d6(home_fans_roll, rng, "local")
    away_fans_die = None if away_outcome == "concede" else _require_2d6(away_fans_roll, rng, "visitante")

    home_side = _apply_side(home, outcome=home_outcome, d6=home_d6, credit=home_credit, fans_roll=home_fans_die)
    away_side = _apply_side(away, outcome=away_outcome, d6=away_d6, credit=away_credit, fans_roll=away_fans_die)

    match.home_winnings_roll = home_d6
    match.away_winnings_roll = away_d6
    match.home_winnings = home_side.winnings
    match.away_winnings = away_side.winnings
    match.home_fans_roll = home_side.fans_roll
    match.away_fans_roll = away_side.fans_roll
    match.home_fans_before = home_side.fans_before
    match.away_fans_before = away_side.fans_before
    match.home_fans_after = home_side.fans_after
    match.away_fans_after = away_side.fans_after
    match.home_gold_discarded = home_side.discarded
    match.away_gold_discarded = away_side.discarded
    match.conceded_by_team_id = conceded_by_team_id
    session.add_all([match, home, away])
    return home_side, away_side


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
