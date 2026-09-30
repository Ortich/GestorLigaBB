from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship

class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    coach_name: str
    race: str
    pin: str = Field(max_length=4) # 4 digits PIN
    treasury: int = Field(default=1_000_000)
    rerolls: int = Field(default=2)
    reroll_cost: int = Field(default=50_000)
    assistant_coaches: int = Field(default=0)
    cheerleaders: int = Field(default=0)
    apothecary: int = Field(default=0) # 0 or 1
    fans: int = Field(default=1) # Dedicated fans (does NOT count towards CTV)
    current_sponsor_id: Optional[str] = Field(default=None)

class Player(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    name: str
    number: int = Field(default=1)
    position: str
    ma: int # Movement Allowance
    st: int # Strength
    ag: str # Agility (e.g. "3+")
    pa: str # Passing Ability (e.g. "4+" or "-")
    av: str # Armour Value (e.g. "9+")
    skills: str = Field(default="") # Comma-separated list of skills
    cost: int = Field(default=50_000)
    current_value: int = Field(default=50_000)
    spp: int = Field(default=0) # Star Player Points
    status: str = Field(default="ACTIVE") # ACTIVE, MNG, DEAD
    injuries: str = Field(default="") # Description of accumulated injuries

class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    round_number: int = Field(default=1, index=True)
    home_team_id: int = Field(foreign_key="team.id", index=True)
    away_team_id: int = Field(foreign_key="team.id", index=True)
    status: str = Field(default="SCHEDULED") # SCHEDULED, READY_CHECK, PRE_MATCH, IN_PROGRESS, COMPLETED
    home_td: int = Field(default=0)
    away_td: int = Field(default=0)
    home_ctv: int = Field(default=0)
    away_ctv: int = Field(default=0)
    petty_cash_amount: int = Field(default=0)
    petty_cash_team_id: Optional[int] = Field(default=None)
    home_petty_spent: int = Field(default=0)
    away_petty_spent: int = Field(default=0)
    home_incentives: str = Field(default="[]") # JSON list of purchased incentives
    away_incentives: str = Field(default="[]") # JSON list of purchased incentives
    weather_roll: Optional[int] = Field(default=None)
    weather_name: Optional[str] = Field(default=None)
    weather_description: Optional[str] = Field(default=None)
    prayers_roll: Optional[int] = Field(default=None)
    prayers_name: Optional[str] = Field(default=None)
    prayers_description: Optional[str] = Field(default=None)
    kick_off_roll: Optional[int] = Field(default=None)
    kick_off_name: Optional[str] = Field(default=None)
    kick_off_description: Optional[str] = Field(default=None)
    bounty_id: Optional[str] = Field(default=None)
    home_coach_ready: bool = Field(default=False)
    away_coach_ready: bool = Field(default=False)
    home_winnings: int = Field(default=0)
    away_winnings: int = Field(default=0)
    mvp_player_id_home: Optional[int] = Field(default=None)
    mvp_player_id_away: Optional[int] = Field(default=None)
    current_turn: int = Field(default=1)
    current_half: int = Field(default=1)

class MatchEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    player_id: Optional[int] = Field(default=None, foreign_key="player.id", index=True)
    event_type: str = Field(index=True) # TD, CAS, FOUL, PASS, INT, MVP
    turn: int = Field(default=1)
    half: int = Field(default=1)
    details: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LeagueState(SQLModel, table=True):
    id: Optional[int] = Field(default=1, primary_key=True)
    league_name: str = Field(default="Liga Blood Bowl BB2020")
    current_round: int = Field(default=1)
    total_rounds: int = Field(default=7)
    active_bounty_id: Optional[str] = Field(default=None)
    master_key: str = Field(default="bbmaster2026")
