import os
import pytest
from starlette.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

# Set temporary database for tests
os.environ["DATABASE_FILE"] = "test_bloodbowl.db"

import database
from database import get_session, create_db_and_tables
from main import app
from seed import seed_database
from models import Team, Player, Match, MatchEvent, LeagueState

# Use a test SQLite database
test_engine = create_engine("sqlite:///test_bloodbowl.db", echo=False, connect_args={"check_same_thread": False})
database.engine = test_engine

def override_get_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    create_db_and_tables()
    seed_database(reset=True)
    yield
    # Cleanup
    if os.path.exists("test_bloodbowl.db"):
        os.remove("test_bloodbowl.db")

@pytest.fixture
def client():
    return TestClient(app)

def test_get_rules(client):
    response = client.get("/api/rules")
    assert response.status_code == 200
    data = response.json()
    assert "weather_table" in data
    assert "kick_off_table" in data
    assert "incentives_catalog" in data
    assert "sponsors" in data

def test_get_league(client):
    response = client.get("/api/league")
    assert response.status_code == 200
    data = response.json()
    assert data["current_round"] == 1
    assert len(data["standings"]) == 8

def test_login_coach(client):
    # Team 1 is Reikland Reavers with PIN 1111
    res = client.post("/api/auth/login", json={"team_id": 1, "pin": "1111"})
    assert res.status_code == 200
    assert res.json()["coach_name"] == "Coach Miller"

    # Bad PIN
    res_bad = client.post("/api/auth/login", json={"team_id": 1, "pin": "9999"})
    assert res_bad.status_code == 400

def test_login_admin(client):
    res = client.post("/api/auth/admin", json={"master_key": "bbmaster2026"})
    assert res.status_code == 200
    assert res.json()["role"] == "admin"

    res_bad = client.post("/api/auth/admin", json={"master_key": "wrong"})
    assert res_bad.status_code == 400

def test_match_assistant_flow(client):
    # Get match 1
    res_m = client.get("/api/matches/1")
    assert res_m.status_code == 200
    m_data = res_m.json()
    assert m_data["match"]["status"] == "SCHEDULED"
    home_id = m_data["match"]["home_team_id"]
    away_id = m_data["match"]["away_team_id"]

    # 1. Ready Check
    # Get PINs dynamically
    team_home = client.get(f"/api/teams/{home_id}").json()["team"]
    team_away = client.get(f"/api/teams/{away_id}").json()["team"]

    # Home check
    # Team 1 PIN is 1111, Team 8 PIN is 8888, etc.
    pin_home = f"{home_id}{home_id}{home_id}{home_id}"
    pin_away = f"{away_id}{away_id}{away_id}{away_id}"

    res_rc1 = client.post("/api/matches/1/ready-check", json={"team_id": home_id, "pin": pin_home})
    assert res_rc1.status_code == 200
    assert res_rc1.json()["home_coach_ready"] is True
    assert res_rc1.json()["match_status"] == "READY_CHECK"

    # Away check
    res_rc2 = client.post("/api/matches/1/ready-check", json={"team_id": away_id, "pin": pin_away})
    assert res_rc2.status_code == 200
    assert res_rc2.json()["away_coach_ready"] is True
    # Transitions to PRE_MATCH!
    assert res_rc2.json()["match_status"] == "PRE_MATCH"
    assert res_rc2.json()["home_ctv"] > 0
    assert res_rc2.json()["away_ctv"] > 0

    # 2. Rolls
    res_weather = client.post("/api/matches/1/roll", json={"roll_type": "weather", "roll_value": 7})
    assert res_weather.status_code == 200
    assert "Clima Perfecto" in res_weather.json()["name"]

    res_kick = client.post("/api/matches/1/roll", json={"roll_type": "kick_off", "roll_value": 10})
    assert res_kick.status_code == 200
    assert "Blitz" in res_kick.json()["name"]

    res_prayers = client.post("/api/matches/1/roll", json={"roll_type": "prayers", "roll_value": 13})
    assert res_prayers.status_code == 200
    assert "Bendición de Nuffle" in res_prayers.json()["name"]

    # 3. Start Match
    res_start = client.post("/api/matches/1/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "IN_PROGRESS"

    # 4. Match Events
    # Fetch player to score TD
    m_after_start = client.get("/api/matches/1").json()
    player_home = m_after_start["home_players"][0]
    initial_spp = player_home["spp"]

    res_ev_td = client.post("/api/matches/1/events", json={
        "team_id": home_id,
        "player_id": player_home["id"],
        "event_type": "TD",
        "turn": 3,
        "half": 1
    })
    assert res_ev_td.status_code == 200
    assert res_ev_td.json()["home_td"] == 1
    assert res_ev_td.json()["spp_awarded"] == 3

    # Check player SPP updated
    res_team = client.get(f"/api/teams/{home_id}").json()
    p_updated = next(p for p in res_team["players"] if p["id"] == player_home["id"])
    assert p_updated["spp"] == initial_spp + 3

    # Event CAS
    res_ev_cas = client.post("/api/matches/1/events", json={
        "team_id": home_id,
        "player_id": player_home["id"],
        "event_type": "CAS",
        "turn": 4,
        "half": 1
    })
    assert res_ev_cas.status_code == 200
    event_id = res_ev_cas.json()["event"]["id"]

    # Delete CAS event to test rollback
    res_del = client.delete(f"/api/matches/1/events/{event_id}")
    assert res_del.status_code == 200

    # 5. Complete Match
    res_comp = client.post("/api/matches/1/complete", json={
        "home_winnings_roll": 5,
        "away_winnings_roll": 4,
        "mvp_player_id_home": player_home["id"],
        "mvp_player_id_away": m_after_start["away_players"][0]["id"]
    })
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "COMPLETED"
    assert res_comp.json()["home_winnings"] == 50_000
    assert res_comp.json()["away_winnings"] == 40_000

def test_admin_endpoints(client):
    headers = {"x-master-key": "bbmaster2026"}

    # 1. Update team treasury
    res_tr = client.post("/api/admin/teams/1/treasury", json={"amount": 50_000}, headers=headers)
    assert res_tr.status_code == 200

    # 2. Update player status (Revive player)
    res_pl = client.post("/api/admin/players/1/status", json={"status": "ACTIVE", "spp_delta": 2}, headers=headers)
    assert res_pl.status_code == 200
    assert res_pl.json()["player"]["status"] == "ACTIVE"

    # 3. Force match status
    res_st = client.post("/api/admin/matches/2/force-status", json={"status": "IN_PROGRESS"}, headers=headers)
    assert res_st.status_code == 200
    assert res_st.json()["new_status"] == "IN_PROGRESS"

    # 4. Update score manually
    res_sc = client.post("/api/admin/matches/2/update-score", json={"home_td": 2, "away_td": 1}, headers=headers)
    assert res_sc.status_code == 200
    assert res_sc.json()["home_td"] == 2

    # 5. Recalculate
    res_rec = client.post("/api/admin/recalculate", headers=headers)
    assert res_rec.status_code == 200
    assert "standings" in res_rec.json()
