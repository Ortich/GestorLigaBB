import pytest
from sqlmodel import Session, SQLModel, create_engine
from models import Team, Player, Match, MatchEvent, LeagueState
from league_engine import (
    calculate_ctv,
    calculate_petty_cash,
    calculate_mercy_rule_compensation,
    calculate_standings,
    assign_dynamic_sponsors
)

@pytest.fixture
def memory_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

def test_calculate_ctv():
    team = Team(
        id=1,
        name="Humans",
        coach_name="Miller",
        race="Humanos",
        pin="1234",
        treasury=500_000, # Must NOT count
        rerolls=3,
        reroll_cost=50_000, # 150_000
        assistant_coaches=2, # 20_000
        cheerleaders=1, # 10_000
        apothecary=1, # 50_000
        fans=5 # Must NOT count
    )
    players = [
        Player(id=1, team_id=1, name="Active 1", position="L", ma=6, st=3, ag="3+", pa="4+", av="9+", cost=50_000, current_value=50_000, status="ACTIVE"),
        Player(id=2, team_id=1, name="Active 2", position="B", ma=7, st=3, ag="3+", pa="4+", av="9+", cost=85_000, current_value=105_000, status="ACTIVE"),
        Player(id=3, team_id=1, name="Injured MNG", position="L", ma=6, st=3, ag="3+", pa="4+", av="9+", cost=50_000, current_value=50_000, status="MNG"),
        Player(id=4, team_id=1, name="Dead", position="L", ma=6, st=3, ag="3+", pa="4+", av="9+", cost=50_000, current_value=50_000, status="DEAD"),
    ]
    # Active players = 50_000 + 105_000 = 155_000
    # Team staff = 150_000 (RR) + 20_000 (asst) + 10_000 (cheer) + 50_000 (apo) = 230_000
    # Total CTV = 385_000
    ctv = calculate_ctv(team, players)
    assert ctv == 385_000

def test_calculate_petty_cash():
    res = calculate_petty_cash(1_000_000, 1_250_000)
    assert res["beneficiary"] == "home"
    assert res["amount"] == 250_000

    res2 = calculate_petty_cash(1_300_000, 1_100_000)
    assert res2["beneficiary"] == "away"
    assert res2["amount"] == 200_000

    res3 = calculate_petty_cash(1_000_000, 1_000_000)
    assert res3["beneficiary"] is None
    assert res3["amount"] == 0

def test_calculate_mercy_rule_compensation():
    cost = 100_000
    # Round 1
    assert calculate_mercy_rule_compensation(1, 1, cost) == 100_000
    assert calculate_mercy_rule_compensation(1, 2, cost) == 50_000
    assert calculate_mercy_rule_compensation(1, 3, cost) == 25_000
    
    # Round 2
    assert calculate_mercy_rule_compensation(2, 1, cost) == 100_000
    assert calculate_mercy_rule_compensation(2, 2, cost) == 50_000

    # Round 3 (expired)
    assert calculate_mercy_rule_compensation(3, 1, cost) == 0

def test_calculate_standings_and_tiebreakers(memory_session):
    # Create 3 teams
    t1 = Team(id=1, name="Team A", coach_name="C1", race="Humanos", pin="1111")
    t2 = Team(id=2, name="Team B", coach_name="C2", race="Orcos", pin="2222")
    t3 = Team(id=3, name="Team C", coach_name="C3", race="Elfos", pin="3333")
    memory_session.add_all([t1, t2, t3])
    memory_session.commit()

    # Match 1: Team A vs Team B -> 2 - 1 (A wins 3pts, B loses by 1 TD -> 1pt)
    m1 = Match(id=1, round_number=1, home_team_id=1, away_team_id=2, home_td=2, away_td=1, status="COMPLETED")
    # Match 2: Team B vs Team C -> 3 - 0 (B wins 3pts, C loses by >1 TD -> 0pts)
    m2 = Match(id=2, round_number=1, home_team_id=2, away_team_id=3, home_td=3, away_td=0, status="COMPLETED")
    memory_session.add_all([m1, m2])
    memory_session.commit()

    # Events: Team B caused 2 casualties, Team A caused 1 casualty
    ev1 = MatchEvent(id=1, match_id=1, team_id=2, event_type="CAS")
    ev2 = MatchEvent(id=2, match_id=1, team_id=2, event_type="CAS")
    ev3 = MatchEvent(id=3, match_id=1, team_id=1, event_type="CAS")
    memory_session.add_all([ev1, ev2, ev3])
    memory_session.commit()

    standings = calculate_standings(memory_session)
    assert len(standings) == 3

    # Team B: played 2, won 1, lost 1 (by 1 TD). Total pts = 3 + 1 = 4 pts. TD: 4 - 2 (+2). Rank 1.
    assert standings[0]["team_id"] == 2
    assert standings[0]["pts"] == 4
    assert standings[0]["rank"] == 1

    # Team A: played 1, won 1. Total pts = 3 pts. Rank 2.
    assert standings[1]["team_id"] == 1
    assert standings[1]["pts"] == 3
    assert standings[1]["rank"] == 2

    # Team C: played 1, lost 1 by 3 TDs. Total pts = 0 pts. Rank 3.
    assert standings[2]["team_id"] == 3
    assert standings[2]["pts"] == 0
    assert standings[2]["rank"] == 3

def test_assign_dynamic_sponsors(memory_session):
    # Setup 4 teams
    teams = [
        Team(id=1, name="T1", coach_name="C1", race="Humanos", pin="1111"),
        Team(id=2, name="T2", coach_name="C2", race="Orcos", pin="2222"),
        Team(id=3, name="T3", coach_name="C3", race="Elfos", pin="3333"),
        Team(id=4, name="T4", coach_name="C4", race="Enanos", pin="4444"),
    ]
    memory_session.add_all(teams)
    memory_session.commit()

    # Matches for Round 3
    # T1 beats T4: 3 - 0
    m1 = Match(id=1, round_number=1, home_team_id=1, away_team_id=4, home_td=3, away_td=0, status="COMPLETED")
    # T2 beats T3: 2 - 1
    m2 = Match(id=2, round_number=1, home_team_id=2, away_team_id=3, home_td=2, away_td=1, status="COMPLETED")
    memory_session.add_all([m1, m2])
    memory_session.commit()

    # Events: T4 has most fouls (Sindicato Malhechores) and worst standing / worst TD diff
    ev1 = MatchEvent(id=1, match_id=1, team_id=4, event_type="FOUL")
    ev2 = MatchEvent(id=2, match_id=1, team_id=4, event_type="FOUL")
    # T2 has most CAS
    ev3 = MatchEvent(id=3, match_id=2, team_id=2, event_type="CAS")
    ev4 = MatchEvent(id=4, match_id=2, team_id=2, event_type="CAS")
    memory_session.add_all([ev1, ev2, ev3, ev4])
    memory_session.commit()

    # In round 2: sponsors should not be assigned
    sponsors_r2 = assign_dynamic_sponsors(memory_session, current_round=2)
    assert sponsors_r2 == {}

    # In round 3: sponsors should be assigned
    sponsors_r3 = assign_dynamic_sponsors(memory_session, current_round=3)
    assert len(sponsors_r3) > 0
    # Check that T4 (last in table) gets a sponsor
    assert "prensa_amarilla" in sponsors_r3
    # Check that Carnicería Da Boyz goes to T2 (most CAS)
    assert sponsors_r3["carniceria_da_boyz"] == 2
