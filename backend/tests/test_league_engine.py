from __future__ import annotations

from sqlmodel import select

from app import league_engine
from app.models import (
    CasualtyResult,
    ChronicleEntry,
    ChronicleKind,
    EventType,
    Match,
    MatchEvent,
    MatchStatus,
    PlayerStatus,
    Sponsor,
    Team,
)
from app.schemas import SponsorAssignment
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


def test_la_cronica_de_patrocinadores_empieza_en_la_jornada_3(session):
    team = make_team(session, "Alpha")
    assignment = SponsorAssignment(
        sponsor_code="PRENSA_AMARILLA",
        sponsor_name="Prensa Amarilla",
        team_id=team.id,
        team_name=team.name,
        metric="standings",
        metric_value=0,
        reason="ultimo de la tabla",
    )

    assert league_engine.write_sponsor_chronicle(session, 2, [assignment]) == []
    session.commit()
    assert session.exec(select(ChronicleEntry)).all() == []

    league_engine.write_sponsor_chronicle(session, 3, [assignment])
    session.commit()
    league_engine.write_sponsor_chronicle(session, 3, [assignment])
    session.commit()

    rows = session.exec(select(ChronicleEntry).where(ChronicleEntry.round_number == 3)).all()
    assert len(rows) == 1
    assert rows[0].kind == ChronicleKind.SPONSOR
    assert rows[0].headline == "Prensa Amarilla se queda con Alpha (ultimo de la tabla)."


def test_la_cronica_del_partido_se_reescribe_y_omite_el_ruido(session):
    home = make_team(session, "Reavers")
    away = make_team(session, "Gouged Eye")
    scorer = add_players(session, home, 1)[0]
    victim = add_players(session, away, 1)[0]
    match = make_match(
        session, home, away, 1, status=MatchStatus.COMPLETED, home_td=1, away_td=0
    )
    match.home_mvp_player_id = scorer.id
    session.add(match)
    session.add(
        MatchEvent(
            match_id=match.id, team_id=home.id, player_id=scorer.id, event_type=EventType.TD
        )
    )
    session.add(
        MatchEvent(
            match_id=match.id, team_id=home.id, player_id=scorer.id, event_type=EventType.PASS
        )
    )
    session.add(
        MatchEvent(
            match_id=match.id,
            team_id=home.id,
            player_id=scorer.id,
            victim_player_id=victim.id,
            event_type=EventType.CAS,
            casualty_result=CasualtyResult.BADLY_HURT,
        )
    )
    session.commit()

    def economy(team: Team, fans_before: int, fans_after: int) -> league_engine.SideEconomy:
        return league_engine.SideEconomy(
            team_id=team.id or 0,
            team_name=team.name,
            winnings_roll=4,
            fans_used=1,
            winner_bonus=1,
            winnings=60_000,
            discarded=0,
            treasury=150_000,
            fans_before=fans_before,
            fans_roll=8,
            fans_after=fans_after,
            conceded=False,
            message="",
        )

    kwargs = dict(
        home_economy=economy(home, 1, 2),
        away_economy=economy(away, 1, 1),
        spills=[],
        payouts=[],
        bounty=None,
    )
    league_engine.write_match_chronicle(session, match, home, away, **kwargs)
    session.commit()
    league_engine.write_match_chronicle(session, match, home, away, **kwargs)
    session.commit()

    rows = session.exec(select(ChronicleEntry).where(ChronicleEntry.match_id == match.id)).all()
    kinds = [row.kind for row in rows]
    assert kinds.count(ChronicleKind.RESULT) == 1
    assert kinds.count(ChronicleKind.TD) == 1
    assert kinds.count(ChronicleKind.MVP) == 1
    assert kinds.count(ChronicleKind.FANS) == 1
    assert ChronicleKind.INJURY not in kinds
    assert all(row.kind != ChronicleKind.TD or "anota" in row.headline for row in rows)


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


def test_ganancias_suman_hinchas_y_el_bono_de_victoria():
    oro, bono = league_engine.winnings_formula(4, 3, "win")
    assert bono == 1
    assert oro == 80_000  # (4 + 1 + 3) × 10.000
    oro_empate, bono_empate = league_engine.winnings_formula(4, 3, "draw")
    assert bono_empate == 0
    assert oro_empate == 70_000
    oro_pierde, _ = league_engine.winnings_formula(4, 3, "loss")
    assert oro_pierde == 70_000


def test_la_aficion_se_mueve_con_el_2d6_y_no_sale_de_1_a_7():
    assert league_engine.next_dedicated_fans(5, "win", 5) == 6
    assert league_engine.next_dedicated_fans(5, "win", 4) == 5
    assert league_engine.next_dedicated_fans(7, "win", 12) == 7
    assert league_engine.next_dedicated_fans(3, "loss", 3) == 2
    assert league_engine.next_dedicated_fans(3, "loss", 4) == 3
    assert league_engine.next_dedicated_fans(1, "loss", 1) == 1
    assert league_engine.next_dedicated_fans(1, "concede", None) == 1
    assert league_engine.next_dedicated_fans(4, "concede", None) == 3
    assert league_engine.next_dedicated_fans(4, "draw", 5) == 5
    assert league_engine.next_dedicated_fans(4, "draw", 3) == 3
    assert league_engine.next_dedicated_fans(4, "draw", 4) == 4


def test_el_titular_de_la_taberna_distingue_al_que_ya_estaba_lleno():
    justo = league_engine.tavern_headline("Reavers", 20_000, 140_000)
    assert "se les fue de las manos" in justo
    assert "20.000 mo" in justo
    desfasado = league_engine.tavern_headline("Reavers", 80_000, 150_000)
    assert "tan desfasado que la fiesta se les fue de madre" in desfasado
    assert "80.000 mo" in desfasado


def test_la_perdida_de_oro_queda_registrada_y_no_se_duplica(session):
    from sqlmodel import select

    from app.models import TreasurySpill

    home = make_team(session, "Local", fans=1, treasury=150_000)
    away = make_team(session, "Visitante", fans=1, treasury=10_000)
    match = make_match(session, home, away, 4, home_td=2, away_td=0)
    home_side, away_side = league_engine.process_post_match_economy(
        session,
        match,
        home,
        away,
        home_winnings_roll=4,
        away_winnings_roll=1,
        home_fans_roll=7,
        away_fans_roll=8,
    )
    league_engine.record_treasury_spills(session, match, home_side, away_side)
    session.commit()
    league_engine.record_treasury_spills(session, match, home_side, away_side)
    session.commit()

    rows = session.exec(select(TreasurySpill).where(TreasurySpill.match_id == match.id)).all()
    assert len(rows) == 1
    assert rows[0].team_id == home.id
    assert rows[0].round_number == 4
    assert rows[0].gold_lost == home_side.discarded
    assert rows[0].gold_lost == 60_000  # (4+1+1)×10.000, ya estaban en 150.000
    assert rows[0].treasury_before == 150_000
    assert "fiesta se les fue de madre" in rows[0].headline
    assert away_side.discarded == 0


def test_el_cierre_economico_respeta_el_tope_y_el_orden(session):
    home = make_team(session, "Local", fans=2, treasury=140_000)
    away = make_team(session, "Visitante", fans=1, treasury=20_000)
    match = make_match(session, home, away, 1, home_td=2, away_td=1)
    home_side, away_side = league_engine.process_post_match_economy(
        session,
        match,
        home,
        away,
        home_winnings_roll=3,
        away_winnings_roll=6,
        home_fans_roll=8,
        away_fans_roll=2,
    )
    # Ganador: (3+1+2)×10.000 = 60.000. 140.000 + 60.000 se queda en 150.000.
    assert home_side.winnings == 60_000
    assert home_side.discarded == 50_000
    assert home.treasury == 150_000
    assert home.fans == 3  # 8 >= 2
    # Perdedor: (6+1)×10.000 = 70.000. 20.000 + 70.000 no llega al tope.
    assert away_side.winnings == 70_000
    assert away_side.discarded == 0
    assert away.treasury == 90_000
    assert away.fans == 1  # 2 <= 1 es falso, no baja


def test_ultima_jornada_completa(session):
    alpha = make_team(session, "Alpha")
    beta = make_team(session, "Beta")
    make_match(session, alpha, beta, 1, status=MatchStatus.COMPLETED)
    make_match(session, beta, alpha, 2, status=MatchStatus.IN_PROGRESS)

    assert league_engine.last_fully_completed_round(session) == 1
