from __future__ import annotations

from sqlmodel import select

from app import league_engine
from app.models import EventType, Match, MatchEvent, MatchStatus, PlayerStatus, Sponsor, Team
from tests.conftest import add_players, make_match, make_team, seed_sponsors


# --------------------------------------------------------------------------- #
# VAE / CTV
# --------------------------------------------------------------------------- #
def test_ctv_suma_plantilla_y_staff(session):
    team = make_team(
        session,
        "Reavers",
        rerolls=2,
        reroll_cost=50_000,
        assistant_coaches=2,
        cheerleaders=3,
        apothecary=True,
        treasury=250_000,
        fans=6,
    )
    add_players(session, team, 11, value=60_000)

    ctv = league_engine.compute_ctv(session, team)

    assert ctv.players == 660_000
    assert ctv.rerolls == 100_000
    assert ctv.assistant_coaches == 20_000
    assert ctv.cheerleaders == 30_000
    assert ctv.apothecary == 50_000
    # Ni la tesoreria (250k) ni los hinchas suman a la VAE.
    assert ctv.total == 860_000


def test_ctv_excluye_mng_y_muertos(session):
    team = make_team(session, "Reavers", rerolls=0, treasury=0)
    players = add_players(session, team, 4, value=100_000)
    players[0].status = PlayerStatus.MNG
    players[1].status = PlayerStatus.DEAD
    session.add_all(players[:2])
    session.commit()

    ctv = league_engine.compute_ctv(session, team)

    assert ctv.total == 200_000
    assert ctv.excluded_players == 2


# --------------------------------------------------------------------------- #
# Petty Cash
# --------------------------------------------------------------------------- #
def test_petty_cash_va_al_equipo_de_menor_vae():
    amount, team_id = league_engine.petty_cash_for(1_200_000, 1_000_000, home_team_id=1, away_team_id=2)
    assert (amount, team_id) == (200_000, 2)


def test_petty_cash_cero_si_hay_empate_de_vae():
    assert league_engine.petty_cash_for(900_000, 900_000, 1, 2) == (0, None)


# --------------------------------------------------------------------------- #
# Puntuacion
# --------------------------------------------------------------------------- #
def test_puntos_por_resultado():
    assert league_engine.match_points(3, 1) == 3  # victoria
    assert league_engine.match_points(2, 2) == 1  # empate
    assert league_engine.match_points(1, 2) == 1  # derrota por 1 TD
    assert league_engine.match_points(0, 2) == 0  # derrota por mas de 1 TD
    assert league_engine.match_points(0, 5) == 0


def test_clasificacion_desempata_por_diferencia_de_td_y_bajas(session):
    alpha = make_team(session, "Alpha")
    beta = make_team(session, "Beta")
    gamma = make_team(session, "Gamma")
    delta = make_team(session, "Delta")
    for team in (alpha, beta, gamma, delta):
        add_players(session, team, 11)

    # Alpha y Beta ganan 2-0; Gamma y Delta pierden.
    make_match(session, alpha, gamma, 1, status=MatchStatus.COMPLETED, home_td=2, away_td=0)
    make_match(session, beta, delta, 1, status=MatchStatus.COMPLETED, home_td=2, away_td=0)
    # Segunda jornada: Alpha gana 1-0, Beta gana 3-0 -> Beta tiene mejor diferencia.
    make_match(session, alpha, delta, 2, status=MatchStatus.COMPLETED, home_td=1, away_td=0)
    make_match(session, beta, gamma, 2, status=MatchStatus.COMPLETED, home_td=3, away_td=0)

    standings = league_engine.compute_standings(session)

    assert [row.team_name for row in standings[:2]] == ["Beta", "Alpha"]
    assert standings[0].points == standings[1].points == 6
    assert standings[0].td_diff == 5
    assert standings[1].td_diff == 3


def test_clasificacion_desempata_por_bajas_cuando_los_td_empatan(session):
    alpha = make_team(session, "Alpha")
    beta = make_team(session, "Beta")
    rival_a = make_team(session, "RivalA")
    rival_b = make_team(session, "RivalB")
    for team in (alpha, beta, rival_a, rival_b):
        add_players(session, team, 11)

    match_a = make_match(session, alpha, rival_a, 1, status=MatchStatus.COMPLETED, home_td=2, away_td=0)
    make_match(session, beta, rival_b, 1, status=MatchStatus.COMPLETED, home_td=2, away_td=0)

    for _ in range(3):
        session.add(MatchEvent(match_id=match_a.id, team_id=alpha.id, event_type=EventType.CAS))
    session.commit()

    standings = league_engine.compute_standings(session)
    assert standings[0].team_name == "Alpha"
    assert standings[0].cas_diff == 3


# --------------------------------------------------------------------------- #
# Patrocinadores dinamicos
# --------------------------------------------------------------------------- #
def _league_with_three_completed_rounds(session) -> list[Team]:
    """4 equipos, 3 jornadas completas y resultados controlados."""
    teams = [make_team(session, name) for name in ("Alpha", "Beta", "Gamma", "Omega")]
    for team in teams:
        add_players(session, team, 11)
    alpha, beta, gamma, omega = teams

    # Alpha arrasa, Omega pierde todo por goleada.
    make_match(session, alpha, omega, 1, status=MatchStatus.COMPLETED, home_td=3, away_td=0)
    make_match(session, beta, gamma, 1, status=MatchStatus.COMPLETED, home_td=2, away_td=1)
    make_match(session, alpha, gamma, 2, status=MatchStatus.COMPLETED, home_td=2, away_td=0)
    make_match(session, beta, omega, 2, status=MatchStatus.COMPLETED, home_td=3, away_td=0)
    make_match(session, alpha, beta, 3, status=MatchStatus.COMPLETED, home_td=1, away_td=0)
    make_match(session, gamma, omega, 3, status=MatchStatus.COMPLETED, home_td=2, away_td=0)
    return teams


def test_sponsors_no_se_asignan_antes_de_la_jornada_3(session):
    seed_sponsors(session)
    teams = [make_team(session, name) for name in ("Alpha", "Beta")]
    for team in teams:
        add_players(session, team, 11)
    make_match(session, teams[0], teams[1], 1, status=MatchStatus.COMPLETED, home_td=1, away_td=0)

    assert league_engine.assign_sponsors(session) == []


def test_sponsors_asignacion_unica_por_equipo(session):
    seed_sponsors(session)
    _league_with_three_completed_rounds(session)

    assignments = league_engine.assign_sponsors(session)
    assigned_teams = [a.team_id for a in assignments if a.team_id is not None]

    assert len(assignments) == 4
    assert len(assigned_teams) == len(set(assigned_teams)), "un equipo no puede tener dos sponsors"

    by_code = {a.sponsor_code: a for a in assignments}
    standings = league_engine.compute_standings(session)
    last_team = standings[-1]
    assert by_code["PRENSA_AMARILLA"].team_id == last_team.team_id


def test_sponsor_colision_respeta_preferencia_del_equipo(session):
    seed_sponsors(session)
    teams = _league_with_three_completed_rounds(session)
    omega = next(t for t in teams if t.name == "Omega")

    # Omega es ultimo y ademas tiene el peor diferencial de TD: colisiona en dos
    # metricas y debe quedarse solo con la que prefiere.
    omega.sponsor_preference = "RINCON_TABERNERO,PRENSA_AMARILLA"
    session.add(omega)
    session.commit()

    assignments = league_engine.assign_sponsors(session)
    by_code = {a.sponsor_code: a for a in assignments}

    assert by_code["RINCON_TABERNERO"].team_id == omega.id
    assert by_code["PRENSA_AMARILLA"].team_id != omega.id
    assert by_code["PRENSA_AMARILLA"].team_id is not None


def test_sponsor_se_persiste_en_el_equipo(session):
    seed_sponsors(session)
    _league_with_three_completed_rounds(session)
    league_engine.assign_sponsors(session)

    with_sponsor = session.exec(select(Team).where(Team.current_sponsor_id.is_not(None))).all()
    assert len(with_sponsor) == 4
    sponsor_ids = [t.current_sponsor_id for t in with_sponsor]
    assert len(set(sponsor_ids)) == 4


def test_carniceria_va_al_equipo_con_mas_bajas(session):
    seed_sponsors(session)
    teams = _league_with_three_completed_rounds(session)
    gamma = next(t for t in teams if t.name == "Gamma")
    match = session.exec(select(Match).where(Match.home_team_id == gamma.id)).first()
    for _ in range(5):
        session.add(MatchEvent(match_id=match.id, team_id=gamma.id, event_type=EventType.CAS))
    session.commit()

    assignments = {a.sponsor_code: a for a in league_engine.assign_sponsors(session)}
    assert assignments["CARNICERIA_DA_BOYZ"].team_id == gamma.id


# --------------------------------------------------------------------------- #
# Red de Seguridad de Novatos
# --------------------------------------------------------------------------- #
def test_mercy_rule_tramos():
    assert league_engine.rookie_safety_percentage(0) == 100
    assert league_engine.rookie_safety_percentage(1) == 50
    assert league_engine.rookie_safety_percentage(2) == 25
    assert league_engine.rookie_safety_percentage(7) == 25

    assert league_engine.rookie_safety_payout(0, 80_000) == 80_000
    assert league_engine.rookie_safety_payout(1, 80_000) == 40_000
    assert league_engine.rookie_safety_payout(2, 80_000) == 20_000


def test_mercy_rule_solo_en_jornadas_1_y_2(session):
    state = league_engine.get_league_state(session)
    assert league_engine.rookie_safety_active(1, state) is True
    assert league_engine.rookie_safety_active(2, state) is True
    assert league_engine.rookie_safety_active(3, state) is False


# --------------------------------------------------------------------------- #
# Recalculo
# --------------------------------------------------------------------------- #
def test_recalculo_regenera_marcadores_desde_los_eventos(session):
    seed_sponsors(session)
    alpha = make_team(session, "Alpha")
    beta = make_team(session, "Beta")
    add_players(session, alpha, 11)
    add_players(session, beta, 11)

    match = make_match(session, alpha, beta, 1, status=MatchStatus.COMPLETED, home_td=9, away_td=9)
    session.add(MatchEvent(match_id=match.id, team_id=alpha.id, event_type=EventType.TD))
    session.add(MatchEvent(match_id=match.id, team_id=alpha.id, event_type=EventType.TD))
    session.add(MatchEvent(match_id=match.id, team_id=beta.id, event_type=EventType.TD))
    session.commit()

    report = league_engine.recalculate_league(session)
    session.refresh(match)

    assert match.home_td == 2
    assert match.away_td == 1
    assert report["matches_fixed"][0]["before"] == "9-9"
    assert report["matches_fixed"][0]["after"] == "2-1"


def test_ultima_jornada_completa(session):
    alpha = make_team(session, "Alpha")
    beta = make_team(session, "Beta")
    make_match(session, alpha, beta, 1, status=MatchStatus.COMPLETED)
    make_match(session, beta, alpha, 2, status=MatchStatus.IN_PROGRESS)

    assert league_engine.last_fully_completed_round(session) == 1
