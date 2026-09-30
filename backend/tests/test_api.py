PINS = {
    "Leones de Altdorf": "1111",
    "Colmillos de Hierro": "2222",
    "Hojas de Laurelorn": "3333",
    "Yunque de Barak Varr": "4444",
    "Plaga de Crookback": "5555",
    "Sombras de Naggaroth": "6666",
    "Tumba de Morr": "7777",
    "Elegidos del Caos": "8888",
}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client, name: str):
    teams = client.get("/api/teams").json()
    team = next(item for item in teams if item["name"] == name)
    response = client.post("/api/auth/login", json={"team_id": team["id"], "pin": PINS[name]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert "pin" not in body["team"]
    return body["token"], team


def test_login_rejects_a_bad_pin(client):
    teams = client.get("/api/teams").json()
    response = client.post(
        "/api/auth/login",
        json={"team_id": teams[0]["id"], "pin": "0000"},
    )
    assert response.status_code == 401
    assert "PIN" in response.json()["detail"]


def test_mng_drops_out_of_ctv(client):
    token, _team = login(client, "Leones de Altdorf")
    dash = client.get("/api/dashboard", headers=auth(token)).json()
    before = dash["ctv"]["total"]
    player = dash["roster"][0]
    admin = client.post("/api/admin/login", json={"master_key": "test-master"}).json()["token"]
    changed = client.post(
        f"/api/admin/players/{player['id']}/status",
        headers=auth(admin),
        json={"status": "MNG"},
    )
    assert changed.status_code == 200
    after = client.get("/api/dashboard", headers=auth(token)).json()
    assert after["ctv"]["total"] == before - player["current_value"]
    revived = client.post(
        f"/api/admin/players/{player['id']}/status",
        headers=auth(admin),
        json={"status": "ACTIVE"},
    )
    assert revived.status_code == 200
    restored = client.get("/api/dashboard", headers=auth(token)).json()
    assert restored["ctv"]["total"] == before


def _open_match(client, token, match_id, home_id, away_id):
    bad = client.post(
        f"/api/matches/{match_id}/ready",
        headers=auth(token),
        json={"team_id": home_id, "pin": "0000"},
    )
    assert bad.status_code == 401
    early = client.post(f"/api/matches/{match_id}/begin", headers=auth(token))
    assert early.status_code == 400
    first = client.post(
        f"/api/matches/{match_id}/ready",
        headers=auth(token),
        json={"team_id": home_id, "pin": PINS[_pin_of(client, home_id)]},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "READY_CHECK"
    second = client.post(
        f"/api/matches/{match_id}/ready",
        headers=auth(token),
        json={"team_id": away_id, "pin": PINS[_pin_of(client, away_id)]},
    )
    assert second.status_code == 200
    state = second.json()
    assert state["status"] == "PRE_MATCH"
    assert state["home"]["ctv"] + state["away"]["ctv"] > 0
    gap = abs(state["home"]["ctv"] - state["away"]["ctv"])
    assert state["petty_cash_amount"] == gap
    if gap == 0:
        assert state["petty_cash_team_id"] is None
    else:
        lower = home_id if state["home"]["ctv"] < state["away"]["ctv"] else away_id
        assert state["petty_cash_team_id"] == lower
    return state


def _pin_of(client, team_id: int) -> str:
    teams = client.get("/api/teams").json()
    team = next(item for item in teams if item["id"] == team_id)
    return team["name"]


def test_match_flow_points_mercy_and_admin_tools(client):
    token, team = login(client, "Leones de Altdorf")
    dash = client.get("/api/dashboard", headers=auth(token)).json()
    assert dash["current_round"] == 1
    assert len(dash["roster"]) == 11
    match = dash["next_match"]
    assert match is not None
    home_id = match["home_team_id"]
    away_id = match["away_team_id"]
    assert team["id"] in (home_id, away_id)

    state = _open_match(client, token, match["id"], home_id, away_id)
    rejected = client.post(
        f"/api/matches/{match['id']}/inducements",
        headers=auth(token),
        json={"team_id": state["petty_cash_team_id"] or home_id, "items": [{"id": "bribe", "qty": 4}]},
    )
    assert rejected.status_code == 400
    other = away_id if state["petty_cash_team_id"] == home_id else home_id
    if state["petty_cash_team_id"] is not None:
        blocked = client.post(
            f"/api/matches/{match['id']}/inducements",
            headers=auth(token),
            json={"team_id": other, "items": [{"id": "temp_cheer", "qty": 1}]},
        )
        assert blocked.status_code == 400
        if state["petty_cash_amount"] >= 20_000:
            bought = client.post(
                f"/api/matches/{match['id']}/inducements",
                headers=auth(token),
                json={
                    "team_id": state["petty_cash_team_id"],
                    "items": [{"id": "temp_cheer", "qty": 1}],
                },
            )
            assert bought.status_code == 200
            assert bought.json()["petty_cash_spent"] == 20_000
            assert bought.json()["petty_cash_remaining"] == state["petty_cash_amount"] - 20_000

    rolled = client.post(
        f"/api/matches/{match['id']}/rolls",
        headers=auth(token),
        json={
            "weather_manual": 7,
            "prayer_manual": 4,
            "kickoff_manual": 9,
            "kicking_team_id": home_id,
        },
    )
    assert rolled.status_code == 200
    assert rolled.json()["weather"]["name"] == "Tiempo perfecto"
    assert rolled.json()["prayer"]["roll"] == 4
    started = client.post(f"/api/matches/{match['id']}/begin", headers=auth(token))
    assert started.status_code == 200
    live = started.json()
    assert live["status"] == "IN_PROGRESS"

    home_players = [player for player in live["home"]["players"] if player["status"] == "ACTIVE"]
    away_players = [player for player in live["away"]["players"] if player["status"] == "ACTIVE"]
    scorer = home_players[0]
    mvp_home = home_players[1]
    mvp_away = away_players[0]
    victim = home_players[2]
    scored = client.post(
        f"/api/matches/{match['id']}/events",
        headers=auth(token),
        json={"team_id": home_id, "player_id": scorer["id"], "event_type": "TD", "turn": 3},
    )
    assert scored.status_code == 200
    assert scored.json()["home_td"] == 1
    assert next(player["spp"] for player in scored.json()["home"]["players"] if player["id"] == scorer["id"]) == 4

    undone = client.post(f"/api/matches/{match['id']}/events/undo", headers=auth(token))
    assert undone.status_code == 200
    assert undone.json()["home_td"] == 0

    scored = client.post(
        f"/api/matches/{match['id']}/events",
        headers=auth(token),
        json={"team_id": home_id, "player_id": scorer["id"], "event_type": "TD", "turn": 3},
    )
    assert scored.status_code == 200
    mng = client.post(
        f"/api/matches/{match['id']}/events",
        headers=auth(token),
        json={"team_id": home_id, "player_id": victim["id"], "event_type": "CAS", "turn": 4},
    )
    assert mng.status_code == 200

    treasury_before = {
        side["id"]: side["treasury"] for side in (live["home"], live["away"])
    }
    # El marcador en vivo no cambia la tesorería; la leemos del acta recién empezada.
    closed = client.post(
        f"/api/matches/{match['id']}/complete",
        headers=auth(token),
        json={
            "home_mvp_player_id": mvp_home["id"],
            "away_mvp_player_id": mvp_away["id"],
            "home_winnings_d6": 1,
            "away_winnings_d6": 1,
            "injuries": [{"player_id": victim["id"], "result": "DEAD", "note": "aplastado"}],
        },
    )
    assert closed.status_code == 200, closed.text
    acta = closed.json()
    assert acta["status"] == "COMPLETED"
    assert acta["home_td"] == 1
    assert acta["away_td"] == 0
    assert acta["home_winnings"] == 10_000
    victim_now = next(player for player in acta["home"]["players"] if player["id"] == victim["id"])
    assert victim_now["status"] == "DEAD"
    assert acta["injuries"][0]["mercy_gold"] == victim["current_value"]
    assert acta["home"]["treasury"] == treasury_before[home_id] + 10_000 + victim["current_value"]
    assert acta["away"]["treasury"] == treasury_before[away_id] + 10_000

    standings = client.get("/api/league").json()["standings"]
    home_row = next(row for row in standings if row["team_id"] == home_id)
    away_row = next(row for row in standings if row["team_id"] == away_id)
    assert home_row["points"] == 3
    assert away_row["points"] == 1
    assert home_row["cas_for"] == 1

    again = client.post(
        f"/api/matches/{match['id']}/events",
        headers=auth(token),
        json={"team_id": home_id, "player_id": scorer["id"], "event_type": "TD"},
    )
    assert again.status_code == 400

    admin = client.post("/api/admin/login", json={"master_key": "wrong"}).json()
    assert "token" not in admin
    bad_admin = client.post("/api/admin/login", json={"master_key": "wrong"})
    assert bad_admin.status_code == 401
    admin_token = client.post("/api/admin/login", json={"master_key": "test-master"}).json()["token"]
    event_id = next(event["id"] for event in acta["events"] if event["event_type"] == "TD")
    wiped = client.delete(f"/api/admin/events/{event_id}", headers=auth(admin_token))
    assert wiped.status_code == 200
    assert wiped.json()["home_td"] == 0
    scorer_now = next(player for player in wiped.json()["home"]["players"] if player["id"] == scorer["id"])
    assert scorer_now["spp"] == 0

    standings = client.get("/api/league").json()["standings"]
    home_row = next(row for row in standings if row["team_id"] == home_id)
    away_row = next(row for row in standings if row["team_id"] == away_id)
    assert home_row["points"] == 1
    assert away_row["points"] == 1

    paid = client.post(
        f"/api/admin/teams/{home_id}/treasury",
        headers=auth(admin_token),
        json={"delta": -5000},
    )
    assert paid.status_code == 200
    revived = client.post(
        f"/api/admin/players/{victim['id']}/status",
        headers=auth(admin_token),
        json={"status": "ACTIVE"},
    )
    assert revived.json()["status"] == "ACTIVE"

    reopened = client.post(
        f"/api/admin/matches/{match['id']}/status",
        headers=auth(admin_token),
        json={"status": "IN_PROGRESS"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "IN_PROGRESS"
    rescored = client.patch(
        f"/api/admin/matches/{match['id']}/score",
        headers=auth(admin_token),
        json={"home_td": 2, "away_td": 2},
    )
    assert rescored.json()["home_td"] == 2

    recalc = client.post("/api/admin/recalculate", headers=auth(admin_token), json={})
    assert recalc.status_code == 200
    body = recalc.json()
    assert len(body["assignment"]) == 4
    assert len(set(body["assignment"].values())) == 4
    assert body["log"]
    bottom = [row["team_id"] for row in body["standings"][-4:]]
    assert set(body["assignment"].values()) == set(bottom)


def test_schedule_covers_the_league(client):
    fixtures = client.get("/api/fixtures").json()
    assert len(fixtures) == 28
    assert {row["round_number"] for row in fixtures} == set(range(1, 8))
