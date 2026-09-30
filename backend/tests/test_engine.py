from app.league_engine import (
    assign_sponsors,
    bounty_reward,
    build_standings,
    calculate_ctv,
    mercy_gold,
    petty_cash,
    points_for_result,
    round_robin,
)
from app.seed import TEAMS


class Obj:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_seed_has_eight_full_rosters():
    assert len(TEAMS) == 8
    pins = set()
    for team in TEAMS:
        assert len(team["players"]) == 11
        assert len(team["pin"]) == 4 and team["pin"].isdigit()
        pins.add(team["pin"])
    assert len(pins) == 8


def test_ctv_ignores_treasury_fans_mng_and_dead():
    team = Obj(
        rerolls=2,
        reroll_cost=50_000,
        assistant_coaches=1,
        cheerleaders=2,
        apothecary=1,
        fans=9,
        treasury=1_000_000,
    )
    players = [
        Obj(id=1, name="Activo", status="ACTIVE", current_value=100_000),
        Obj(id=2, name="Lesionado", status="MNG", current_value=80_000),
        Obj(id=3, name="Muerto", status="DEAD", current_value=70_000),
    ]
    breakdown = calculate_ctv(team, players)
    assert breakdown["players"] == 100_000
    assert breakdown["rerolls"] == 100_000
    assert breakdown["assistants"] == 10_000
    assert breakdown["cheerleaders"] == 20_000
    assert breakdown["apothecary"] == 50_000
    assert breakdown["total"] == 280_000
    assert {item["name"] for item in breakdown["excluded_players"]} == {"Lesionado", "Muerto"}


def test_petty_cash_is_the_exact_gap():
    assert petty_cash(900_000, 900_000) == (None, 0)
    assert petty_cash(800_000, 950_000) == ("home", 150_000)
    assert petty_cash(1_100_000, 900_000) == ("away", 200_000)


def test_points_house_rule():
    assert points_for_result(2, 0) == 3
    assert points_for_result(0, 2) == 0
    assert points_for_result(1, 0) == 3
    assert points_for_result(0, 1) == 1
    assert points_for_result(1, 1) == 1


def test_mercy_steps_down():
    assert mercy_gold(80_000, 0) == 80_000
    assert mercy_gold(80_000, 1) == 40_000
    assert mercy_gold(80_000, 2) == 20_000
    assert mercy_gold(80_000, 5) == 20_000


def test_standings_use_three_keys():
    teams = [
        Obj(id=1, name="Alfas", coach_name="A", race="Humanos", race_key="human", current_sponsor_id=None),
        Obj(id=2, name="Betas", coach_name="B", race="Orcos", race_key="orc", current_sponsor_id=None),
        Obj(id=3, name="Gammas", coach_name="C", race="Enanos", race_key="dwarf", current_sponsor_id=None),
    ]
    matches = [
        Obj(id=10, status="COMPLETED", home_team_id=1, away_team_id=2, home_td=1, away_td=0),
        Obj(id=11, status="COMPLETED", home_team_id=3, away_team_id=1, home_td=2, away_td=2),
        Obj(id=12, status="SCHEDULED", home_team_id=2, away_team_id=3, home_td=5, away_td=0),
    ]
    events = [
        Obj(match_id=10, team_id=2, event_type="CAS"),
        Obj(match_id=10, team_id=2, event_type="CAS"),
        Obj(match_id=11, team_id=1, event_type="FOUL"),
    ]
    rows = build_standings(teams, matches, events)
    by_name = {row["name"]: row for row in rows}
    assert [row["name"] for row in rows] == ["Alfas", "Gammas", "Betas"]
    assert by_name["Alfas"]["points"] == 4
    assert by_name["Betas"]["points"] == 1
    assert by_name["Gammas"]["points"] == 1
    assert by_name["Betas"]["cas_for"] == 2
    assert by_name["Alfas"]["cas_against"] == 2
    assert by_name["Alfas"]["fouls"] == 1
    assert by_name["Betas"]["td_for"] == 0
    assert rows[0]["rank"] == 1


def test_sponsor_collision_lets_the_lower_team_pick_first():
    rows = [
        {"team_id": 1, "name": "A", "rank": 1, "td_diff": 5, "cas_for": 1, "fouls": 0},
        {"team_id": 2, "name": "B", "rank": 2, "td_diff": 1, "cas_for": 8, "fouls": 1},
        {"team_id": 3, "name": "C", "rank": 3, "td_diff": -1, "cas_for": 2, "fouls": 6},
        {"team_id": 4, "name": "D", "rank": 4, "td_diff": -8, "cas_for": 1, "fouls": 2},
    ]
    assignment, log = assign_sponsors(rows)
    assert assignment == {"tabernero": 4, "sindicato": 3, "carniceria": 2, "prensa": 1}
    assert any("Colisión" in line for line in log)
    chosen, _ = assign_sponsors(rows, manual={4: "prensa"})
    assert chosen["prensa"] == 4
    assert len(set(chosen.values())) == 4


def test_round_robin_is_a_single_round():
    rounds = round_robin([1, 2, 3, 4, 5, 6, 7, 8])
    assert len(rounds) == 7
    seen = set()
    games = {team: 0 for team in range(1, 9)}
    for pairs in rounds:
        assert len(pairs) == 4
        playing = []
        for home, away in pairs:
            assert home != away
            key = tuple(sorted((home, away)))
            assert key not in seen
            seen.add(key)
            playing.extend(key)
            games[home] += 1
            games[away] += 1
        assert len(playing) == 8
    assert len(seen) == 28
    assert all(count == 7 for count in games.values())


def test_bounty_metrics():
    assert bounty_reward("caza", td=0, cas=2, fouls=0, td_against=3) == 20_000
    assert bounty_reward("caza", td=3, cas=1, fouls=4, td_against=0) == 0
    assert bounty_reward("muro", td=1, cas=0, fouls=0, td_against=0) == 10_000
    assert bounty_reward("festival", td=2, cas=0, fouls=0, td_against=2) == 20_000
    assert bounty_reward("sucio", td=0, cas=0, fouls=2, td_against=1) == 10_000
    assert bounty_reward(None, td=5, cas=5, fouls=5, td_against=0) == 0
