from __future__ import annotations

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    team_id: int
    pin: str = Field(min_length=4, max_length=4)


class ReadyIn(BaseModel):
    team_id: int
    pin: str = Field(min_length=4, max_length=4)


class InducementItemIn(BaseModel):
    id: str
    qty: int = Field(ge=0, le=12)


class InducementsIn(BaseModel):
    team_id: int
    items: list[InducementItemIn]


class RollsIn(BaseModel):
    weather: bool = False
    weather_manual: int | None = None
    prayer: bool = False
    prayer_manual: int | None = None
    kickoff: bool = False
    kickoff_manual: int | None = None
    kicking_team_id: int | None = None


class EventIn(BaseModel):
    team_id: int
    player_id: int
    event_type: str
    turn: int | None = None


class TurnIn(BaseModel):
    turn: int = Field(ge=0, le=16)


class BenefitIn(BaseModel):
    team_id: int
    benefit: str


class InjuryIn(BaseModel):
    player_id: int
    result: str
    note: str = ""


class CompleteIn(BaseModel):
    home_mvp_player_id: int
    away_mvp_player_id: int
    home_winnings_d6: int | None = None
    away_winnings_d6: int | None = None
    injuries: list[InjuryIn] = []


class PlayerUpdateIn(BaseModel):
    name: str | None = None
    skills: str | None = None
    current_value: int | None = None
    ma: int | None = None
    st: int | None = None
    ag: int | None = None
    pa: int | None = None
    av: int | None = None
    clear_pa: bool = False
    injuries: str | None = None


class AdminLoginIn(BaseModel):
    master_key: str


class StatusIn(BaseModel):
    status: str


class ScoreIn(BaseModel):
    home_td: int = Field(ge=0, le=30)
    away_td: int = Field(ge=0, le=30)


class TreasuryIn(BaseModel):
    delta: int


class PlayerStatusIn(BaseModel):
    status: str


class RecalcIn(BaseModel):
    choices: dict[str, str] | None = None
    override: dict[str, int] | None = None


class BountyIn(BaseModel):
    bounty_id: str | None = None


class RoundIn(BaseModel):
    round_number: int = Field(ge=1, le=30)


class PinIn(BaseModel):
    pin: str = Field(min_length=4, max_length=4)
