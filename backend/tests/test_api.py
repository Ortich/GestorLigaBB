from __future__ import annotations

import pytest
from sqlmodel import select

from app.models import (
    CasualtyResult,
    EventType,
    Match,
    MatchStatus,
    Player,
    PlayerStatus,
    Team,
)
from tests.conftest import add_players, ensure_state, make_match, make_team

MASTER = {"X-Master-Key": "test-master-key"}


def auth(client, team_id: int, pin: str = "1234") -> dict[str, str]:
    response = client.post("/api/auth/login", json={"team_id": team_id, "pin": pin})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def duel(session):
    """Dos equipos con VAE distinta y un partido programado en la jornada 1."""
    home = make_team(session, "Reavers", pin="1111", rerolls=3, reroll_cost=50_000)
    away = make_team(session, "Gouged Eye", pin="2222", rerolls=1, reroll_cost=50_000)
    add_players(session, home, 11, value=60_000)
    add_players(session, away, 11, value=50_000)
    match = make_match(session, home, away, round_number=1)
    ensure_state(session, current_round=1, total_rounds=7)
    return {"home": home, "away": away, "match": match}


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
def test_login_con_pin_correcto(client, duel):
    response = client.post("/api/auth/login", json={"team_id": duel["home"].id, "pin": "1111"})
    assert response.status_code == 200
    assert response.json()["team_name"] == "Reavers"


def test_login_con_pin_incorrecto(client, duel):
    response = client.post("/api/auth/login", json={"team_id": duel["home"].id, "pin": "9999"})
    assert response.status_code == 403
    assert "PIN" in response.json()["detail"]


def test_login_valida_formato_de_pin(client, duel):
    response = client.post("/api/auth/login", json={"team_id": duel["home"].id, "pin": "12"})
    assert response.status_code == 422


def test_el_desplegable_de_login_no_expone_el_pin(client, duel):
    payload = client.get("/api/auth/teams").json()
    assert len(payload) == 2
    assert all("pin" not in str(key) for item in payload for key in item)


def test_endpoints_protegidos_sin_token(client, duel):
    response = client.post(f"/api/matches/{duel['match'].id}/ready-check")
    assert response.status_code == 401


# --------------------------------------------------------------------------- #
# Maquina de estados del partido
# --------------------------------------------------------------------------- #
def test_flujo_completo_de_partido(client, session, duel):
    home, away, match = duel["home"], duel["away"], duel["match"]
    headers = auth(client, home.id, "1111")

    # 1. READY CHECK: hacen falta los dos PIN.
    response = client.post(f"/api/matches/{match.id}/ready-check", headers=headers)
    assert response.json()["status"] == "READY_CHECK"

    response = client.post(
        f"/api/matches/{match.id}/confirm", headers=headers, json={"team_id": home.id, "pin": "1111"}
    )
    assert response.json()["status"] == "READY_CHECK"
    assert response.json()["home_ready"] is True

    response = client.post(
        f"/api/matches/{match.id}/confirm", headers=headers, json={"team_id": away.id, "pin": "2222"}
    )
    detail = response.json()
    assert detail["status"] == "PRE_MATCH"

    # 2. PRE MATCH: VAE y Fondo Menor calculados automaticamente.
    assert detail["home_ctv"] == 11 * 60_000 + 150_000
    assert detail["away_ctv"] == 11 * 50_000 + 50_000
    assert detail["petty_cash_amount"] == detail["home_ctv"] - detail["away_ctv"]
    assert detail["petty_cash_team_id"] == away.id

    # 3. Incentivos: solo el equipo de menor VAE y solo con el Fondo Menor.
    response = client.post(
        f"/api/matches/{match.id}/inducements",
        headers=headers,
        json={"team_id": away.id, "code": "BRIBE", "quantity": 1},
    )
    assert response.status_code == 200
    assert response.json()["petty_cash_remaining"] == detail["petty_cash_amount"] - 100_000

    # 4. Tiradas de prepartido.
    client.post(f"/api/matches/{match.id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 11})
    response = client.post(
        f"/api/matches/{match.id}/rolls", headers=headers, json={"kind": "KICK_OFF", "value": 2}
    )
    body = response.json()
    assert body["weather"]["name"] == "Lluvia Torrencial"
    assert body["kick_off"]["name"] == "A por el Arbitro"

    # 5. IN PROGRESS y registro de eventos en vivo.
    response = client.post(f"/api/matches/{match.id}/start", headers=headers)
    assert response.json()["status"] == "IN_PROGRESS"

    scorer = session.exec(select(Player).where(Player.team_id == home.id)).first()
    victim = session.exec(select(Player).where(Player.team_id == away.id)).first()

    client.post(
        f"/api/matches/{match.id}/events",
        headers=headers,
        json={"team_id": home.id, "event_type": "TD", "player_id": scorer.id, "turn": 4},
    )
    response = client.post(
        f"/api/matches/{match.id}/events",
        headers=headers,
        json={
            "team_id": home.id,
            "event_type": "CAS",
            "player_id": scorer.id,
            "victim_player_id": victim.id,
            "casualty_result": "SERIOUSLY_HURT",
        },
    )
    body = response.json()
    assert body["home_td"] == 1
    assert body["scoreboard"][str(home.id)]["CAS"] == 1

    session.refresh(scorer)
    assert scorer.spp == 5  # 3 por el TD + 2 por la baja

    # 6. Cierre del acta.
    response = client.post(
        f"/api/matches/{match.id}/complete",
        headers=headers,
        json={"home_mvp_player_id": scorer.id, "home_winnings_roll": 4, "away_winnings_roll": 2},
    )
    report = response.json()
    assert report["home_winnings"] == 40_000
    assert report["away_winnings"] == 20_000
    assert report["injuries"][0]["result"] == "SERIOUSLY_HURT"

    session.refresh(scorer)
    session.refresh(victim)
    session.refresh(match)
    assert scorer.spp == 9  # +4 del MVP
    assert victim.status == PlayerStatus.MNG
    assert match.status == MatchStatus.COMPLETED

    standings = client.get("/api/league/standings").json()
    assert standings[0]["team_name"] == "Reavers"
    assert standings[0]["points"] == 3
    assert standings[1]["points"] == 1  # derrota por 1 TD


def test_transicion_invalida_devuelve_400(client, duel):
    headers = auth(client, duel["home"].id, "1111")
    response = client.post(f"/api/matches/{duel['match'].id}/start", headers=headers)
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_transition"


def test_no_se_pueden_registrar_eventos_fuera_de_in_progress(client, duel):
    headers = auth(client, duel["home"].id, "1111")
    response = client.post(
        f"/api/matches/{duel['match'].id}/events",
        headers=headers,
        json={"team_id": duel["home"].id, "event_type": "TD"},
    )
    assert response.status_code == 400


def test_ready_check_rechaza_pin_incorrecto(client, duel):
    headers = auth(client, duel["home"].id, "1111")
    client.post(f"/api/matches/{duel['match'].id}/ready-check", headers=headers)
    response = client.post(
        f"/api/matches/{duel['match'].id}/confirm",
        headers=headers,
        json={"team_id": duel["away"].id, "pin": "0000"},
    )
    assert response.status_code == 403


def test_equipo_ajeno_no_puede_gestionar_el_partido(client, session, duel):
    intruder = make_team(session, "Intrusos", pin="9999")
    add_players(session, intruder, 11)
    headers = auth(client, intruder.id, "9999")
    response = client.post(f"/api/matches/{duel['match'].id}/ready-check", headers=headers)
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Incentivos / Fondo Menor
# --------------------------------------------------------------------------- #
def _reach_pre_match(client, duel) -> dict[str, str]:
    headers = auth(client, duel["home"].id, "1111")
    client.post(f"/api/matches/{duel['match'].id}/ready-check", headers=headers)
    client.post(
        f"/api/matches/{duel['match'].id}/confirm",
        headers=headers,
        json={"team_id": duel["home"].id, "pin": "1111"},
    )
    client.post(
        f"/api/matches/{duel['match'].id}/confirm",
        headers=headers,
        json={"team_id": duel["away"].id, "pin": "2222"},
    )
    return headers


def test_el_equipo_de_mayor_vae_no_puede_comprar_incentivos(client, duel):
    headers = _reach_pre_match(client, duel)
    response = client.post(
        f"/api/matches/{duel['match'].id}/inducements",
        headers=headers,
        json={"team_id": duel["home"].id, "code": "BRIBE", "quantity": 1},
    )
    assert response.status_code == 403
    assert "menor VAE" in response.json()["detail"]


def test_no_se_puede_superar_el_fondo_menor(client, duel):
    headers = _reach_pre_match(client, duel)
    # Fondo menor = 210.000 mo; 3 sobornos costarian 300.000 mo.
    response = client.post(
        f"/api/matches/{duel['match'].id}/inducements",
        headers=headers,
        json={"team_id": duel["away"].id, "code": "BRIBE", "quantity": 3},
    )
    assert response.status_code == 400
    assert "Fondo Menor insuficiente" in response.json()["detail"]


def test_respeta_el_maximo_por_incentivo(client, duel):
    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    for _ in range(2):
        assert (
            client.post(
                f"/api/matches/{match_id}/inducements",
                headers=headers,
                json={"team_id": duel["away"].id, "code": "BLOODWEISER_KEG", "quantity": 1},
            ).status_code
            == 200
        )
    response = client.post(
        f"/api/matches/{match_id}/inducements",
        headers=headers,
        json={"team_id": duel["away"].id, "code": "BLOODWEISER_KEG", "quantity": 1},
    )
    assert response.status_code == 400
    assert "Maximo 2" in response.json()["detail"]


def test_incentivo_inexistente(client, duel):
    headers = _reach_pre_match(client, duel)
    response = client.post(
        f"/api/matches/{duel['match'].id}/inducements",
        headers=headers,
        json={"team_id": duel["away"].id, "code": "NO_EXISTE"},
    )
    assert response.status_code == 404


def test_tirada_fuera_de_rango(client, duel):
    headers = _reach_pre_match(client, duel)
    response = client.post(
        f"/api/matches/{duel['match'].id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 13}
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Mercy Rule en el cierre del acta
# --------------------------------------------------------------------------- #
def test_mercy_rule_compensa_la_muerte_en_jornada_1(client, session, duel):
    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)

    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    victims = session.exec(select(Player).where(Player.team_id == duel["away"].id)).all()[:2]
    treasury_before = duel["away"].treasury

    for victim in victims:
        client.post(
            f"/api/matches/{match_id}/events",
            headers=headers,
            json={
                "team_id": duel["home"].id,
                "event_type": "CAS",
                "player_id": killer.id,
                "victim_player_id": victim.id,
                "casualty_result": "DEAD",
            },
        )

    report = client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    ).json()

    payouts = report["rookie_safety_payouts"]
    assert [p["percentage"] for p in payouts] == [100, 50]
    assert [p["gold"] for p in payouts] == [50_000, 25_000]

    session.refresh(duel["away"])
    # 10.000 de ganancias + 50.000 + 25.000 de la red de seguridad
    assert duel["away"].treasury == treasury_before + 10_000 + 75_000
    for victim in victims:
        session.refresh(victim)
        assert victim.status == PlayerStatus.DEAD


def test_sin_mercy_rule_a_partir_de_la_jornada_3(client, session, duel):
    duel["match"].round_number = 3
    session.add(duel["match"])
    session.commit()

    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)

    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    victim = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={
            "team_id": duel["home"].id,
            "event_type": "CAS",
            "player_id": killer.id,
            "victim_player_id": victim.id,
            "casualty_result": "DEAD",
        },
    )
    report = client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    ).json()
    assert report["rookie_safety_payouts"] == []


def test_la_lesion_de_por_vida_no_paga_la_red_de_seguridad(client, session, duel):
    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)

    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    victim = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    treasury_before = duel["away"].treasury
    client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={
            "team_id": duel["home"].id,
            "event_type": "CAS",
            "player_id": killer.id,
            "victim_player_id": victim.id,
            "casualty_result": "LASTING_INJURY_ST",
        },
    )
    report = client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    ).json()
    assert report["rookie_safety_payouts"] == []
    session.refresh(duel["away"])
    assert duel["away"].treasury == treasury_before + 10_000


def test_la_muerte_de_un_mejorado_devuelve_el_valor_actual(client, session, duel):
    """Zombi de 40.000 mejorado hasta 80.000: si muere en la jornada 1 vuelven los 80.000."""
    victim = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    victim.cost = 40_000
    victim.current_value = 80_000
    session.add(victim)
    session.commit()
    treasury_before = duel["away"].treasury

    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)
    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={
            "team_id": duel["home"].id,
            "event_type": "CAS",
            "player_id": killer.id,
            "victim_player_id": victim.id,
            "casualty_result": "DEAD",
        },
    )
    report = client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    ).json()
    assert report["rookie_safety_payouts"][0]["gold"] == 80_000
    assert report["rookie_safety_payouts"][0]["percentage"] == 100
    session.refresh(duel["away"])
    assert duel["away"].treasury == treasury_before + 10_000 + 80_000


def test_despedir_a_un_lesionado_devuelve_solo_el_coste_base(client, session, duel):
    """El mismo zombi, despedido con una lesion de por vida, devuelve 40.000 y no 80.000."""
    victim = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    victim.cost = 40_000
    victim.current_value = 80_000
    session.add(victim)
    session.commit()

    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)
    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={
            "team_id": duel["home"].id,
            "event_type": "CAS",
            "player_id": killer.id,
            "victim_player_id": victim.id,
            "casualty_result": "LASTING_INJURY_ST",
        },
    )
    client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    )
    session.refresh(victim)
    assert victim.status == PlayerStatus.MNG

    away_headers = auth(client, duel["away"].id, "2222")
    treasury_before = client.get(f"/api/teams/{duel['away'].id}").json()["treasury"]
    response = client.delete(
        f"/api/teams/{duel['away'].id}/players/{victim.id}",
        headers=away_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["treasury"] == treasury_before + 40_000
    despedido = next(p for p in body["players"] if p["id"] == victim.id)
    assert despedido["status"] == "RETIRED"
    assert despedido["current_value"] == 80_000
    assert despedido["cost"] == 40_000


def test_lesion_persistente_baja_la_caracteristica(client, session, duel):
    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)

    killer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    victim = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    ma_before = victim.ma

    client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={
            "team_id": duel["home"].id,
            "event_type": "CAS",
            "player_id": killer.id,
            "victim_player_id": victim.id,
            "casualty_result": "LASTING_INJURY_MA",
        },
    )
    client.post(
        f"/api/matches/{match_id}/complete",
        headers=headers,
        json={"home_winnings_roll": 1, "away_winnings_roll": 1},
    )
    session.refresh(victim)
    assert victim.ma == ma_before - 1
    assert victim.status == PlayerStatus.MNG


def test_borrar_evento_revierte_marcador_y_spp(client, session, duel):
    headers = _reach_pre_match(client, duel)
    match_id = duel["match"].id
    client.post(f"/api/matches/{match_id}/rolls", headers=headers, json={"kind": "WEATHER", "value": 7})
    client.post(f"/api/matches/{match_id}/start", headers=headers)

    scorer = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    body = client.post(
        f"/api/matches/{match_id}/events",
        headers=headers,
        json={"team_id": duel["home"].id, "event_type": "TD", "player_id": scorer.id},
    ).json()
    event_id = body["events"][0]["id"]
    assert body["home_td"] == 1

    body = client.delete(f"/api/matches/{match_id}/events/{event_id}", headers=headers).json()
    assert body["home_td"] == 0
    session.refresh(scorer)
    assert scorer.spp == 0


# --------------------------------------------------------------------------- #
# Panel de comisario
# --------------------------------------------------------------------------- #
def test_admin_requiere_master_key(client, duel):
    assert client.get("/api/admin/overview").status_code == 403
    assert client.get("/api/admin/overview", headers={"X-Master-Key": "mala"}).status_code == 403
    assert client.get("/api/admin/overview", headers=MASTER).status_code == 200


def test_admin_puede_reabrir_un_acta_cerrada(client, session, duel):
    duel["match"].status = MatchStatus.COMPLETED
    session.add(duel["match"])
    session.commit()

    response = client.post(
        f"/api/admin/matches/{duel['match'].id}/status", headers=MASTER, json={"status": "IN_PROGRESS"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_admin_ajusta_tesoreria_y_revive_jugadores(client, session, duel):
    player = session.exec(select(Player).where(Player.team_id == duel["away"].id)).first()
    player.status = PlayerStatus.DEAD
    session.add(player)
    session.commit()

    response = client.post(
        f"/api/admin/teams/{duel['away'].id}/treasury", headers=MASTER, json={"delta": 50_000}
    )
    assert response.json()["treasury"] == duel["away"].treasury + 50_000

    response = client.patch(
        f"/api/admin/players/{player.id}", headers=MASTER, json={"status": "ACTIVE"}
    )
    assert response.json()["status"] == "ACTIVE"


def test_admin_no_permite_tesoreria_negativa(client, duel):
    response = client.post(
        f"/api/admin/teams/{duel['home'].id}/treasury", headers=MASTER, json={"delta": -10_000_000}
    )
    assert response.status_code == 400


def test_admin_recalcula_la_liga(client, session, duel):
    from app.models import MatchEvent

    duel["match"].status = MatchStatus.COMPLETED
    duel["match"].home_td = 7
    session.add(duel["match"])
    session.add(MatchEvent(match_id=duel["match"].id, team_id=duel["home"].id, event_type=EventType.TD))
    session.commit()

    report = client.post("/api/admin/recalculate", headers=MASTER).json()
    assert report["matches_fixed"][0]["after"] == "1-0"


# --------------------------------------------------------------------------- #
# Reglas y roster
# --------------------------------------------------------------------------- #
def test_rules_json_expuesto(client):
    body = client.get("/api/rules").json()
    assert body["weather"]["entries"][0]["name"] == "Calor Sofocante"
    assert len(body["prayers_to_nuffle"]["entries"]) == 16
    assert len(body["sponsors"]) == 4


def test_detalle_de_equipo_incluye_vae_desglosada(client, duel):
    body = client.get(f"/api/teams/{duel['home'].id}").json()
    assert body["ctv"]["total"] == 11 * 60_000 + 150_000
    assert len(body["players"]) == 11
    assert body["players"][0]["level"] == "Novato"


def test_equipo_inexistente_devuelve_404(client):
    assert client.get("/api/teams/999").status_code == 404


def test_mejorar_jugador_consume_spp_y_sube_valor(client, session, duel):
    headers = auth(client, duel["home"].id, "1111")
    player = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    player.spp = 6
    session.add(player)
    session.commit()

    response = client.post(
        f"/api/teams/{duel['home'].id}/players/{player.id}/advance",
        headers=headers,
        json={"code": "CHOSEN_PRIMARY", "skill": "Bloqueo"},
    )
    assert response.status_code == 200
    session.refresh(player)
    assert player.spp == 0
    assert player.current_value == 80_000  # 60.000 de base + 20.000 de la mejora
    assert "Bloqueo" in player.skills


def test_mejorar_sin_spp_suficientes(client, session, duel):
    headers = auth(client, duel["home"].id, "1111")
    player = session.exec(select(Player).where(Player.team_id == duel["home"].id)).first()
    response = client.post(
        f"/api/teams/{duel['home'].id}/players/{player.id}/advance",
        headers=headers,
        json={"code": "CHOSEN_SECONDARY", "skill": "Esquivar"},
    )
    assert response.status_code == 400


def test_no_puedes_tocar_el_equipo_de_otro(client, duel):
    headers = auth(client, duel["home"].id, "1111")
    response = client.patch(
        f"/api/teams/{duel['away'].id}", headers=headers, json={"coach_name": "Hackeado"}
    )
    assert response.status_code == 403


def test_proximo_partido_del_equipo(client, duel):
    body = client.get("/api/matches/next", params={"team_id": duel["home"].id}).json()
    assert body["id"] == duel["match"].id
    assert body["away_team_name"] == "Gouged Eye"
