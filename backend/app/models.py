from __future__ import annotations

from sqlmodel import Field, SQLModel


class Team(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    coach_name: str
    race: str
    race_key: str
    pin: str
    treasury: int = 1_000_000
    rerolls: int = 0
    reroll_cost: int = 50_000
    assistant_coaches: int = 0
    cheerleaders: int = 0
    apothecary: int = 0
    fans: int = 1
    current_sponsor_id: str | None = None


class Player(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    name: str
    position: str
    number: int = 0
    ma: int
    st: int
    ag: int
    pa: int | None = None
    av: int
    skills: str = ""
    cost: int
    current_value: int
    spp: int = 0
    status: str = "ACTIVE"
    mng_until_round: int | None = None
    injuries: str = ""


class Match(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    round_number: int = Field(index=True)
    home_team_id: int = Field(foreign_key="team.id", index=True)
    away_team_id: int = Field(foreign_key="team.id", index=True)
    status: str = "SCHEDULED"
    home_td: int = 0
    away_td: int = 0
    home_ctv: int | None = None
    away_ctv: int | None = None
    petty_cash_amount: int = 0
    petty_cash_team_id: int | None = None
    weather_roll: int | None = None
    prayer_roll: int | None = None
    kick_off_roll: int | None = None
    kicking_team_id: int | None = None
    bounty_id: str | None = None
    home_ready: bool = False
    away_ready: bool = False
    home_winnings: int = 0
    away_winnings: int = 0
    home_mvp_player_id: int | None = None
    away_mvp_player_id: int | None = None
    home_free_reroll_used: bool = False
    away_free_reroll_used: bool = False
    home_free_bribe_used: bool = False
    away_free_bribe_used: bool = False
    home_bounty_gold: int = 0
    away_bounty_gold: int = 0
    home_sponsor_gold: int = 0
    away_sponsor_gold: int = 0
    current_turn: int = 1
    closure_applied: bool = False


class MatchEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    player_id: int | None = Field(default=None, foreign_key="player.id")
    event_type: str
    turn: int | None = None
    spp_awarded: int = 0


class MatchInducement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id")
    inducement_id: str
    quantity: int
    unit_cost: int


class PlayerInjury(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    player_id: int = Field(foreign_key="player.id")
    round_number: int
    result: str
    value_at_time: int
    mercy_gold: int = 0
    note: str = ""


class LeagueState(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    current_round: int = 1
    active_bounty_id: str | None = "caza"
    sponsor_log: str = ""
