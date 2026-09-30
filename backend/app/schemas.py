"""Modelos Pydantic de entrada/salida de la API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.models import CasualtyResult, EventType, MatchStatus, PlayerStatus


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    team_id: int
    pin: str

    @field_validator("pin")
    @classmethod
    def _pin_digits(cls, value: str) -> str:
        value = (value or "").strip()
        if not value.isdigit() or len(value) != 4:
            raise ValueError("El PIN debe tener exactamente 4 digitos.")
        return value


class LoginResponse(BaseModel):
    token: str
    team_id: int
    team_name: str


class ChangePinRequest(BaseModel):
    current_pin: str
    new_pin: str


# --------------------------------------------------------------------------- #
# Jugadores y equipos
# --------------------------------------------------------------------------- #
class PlayerPublic(BaseModel):
    id: int
    team_id: int
    number: int
    name: str
    position: str
    ma: int
    st: int
    ag: int
    pa: Optional[int]
    av: int
    skills: list[str]
    cost: int
    current_value: int
    spp: int
    status: PlayerStatus
    level: str
    niggling_injuries: int
    counts_towards_ctv: bool


class CtvBreakdown(BaseModel):
    team_id: int
    players: int
    rerolls: int
    assistant_coaches: int
    cheerleaders: int
    apothecary: int
    total: int
    excluded_players: int


class TeamSummary(BaseModel):
    id: int
    name: str
    coach_name: str
    race: str
    logo: str
    treasury: int
    ctv: int
    current_sponsor_id: Optional[int] = None
    current_sponsor: Optional["SponsorPublic"] = None


class TeamDetail(BaseModel):
    id: int
    name: str
    coach_name: str
    race: str
    logo: str
    treasury: int
    rerolls: int
    reroll_cost: int
    assistant_coaches: int
    cheerleaders: int
    apothecary: bool
    fans: int
    sponsor_preference: list[str]
    rookie_safety_claims: int
    current_sponsor: Optional["SponsorPublic"] = None
    ctv: CtvBreakdown
    players: list[PlayerPublic]


class TeamUpdate(BaseModel):
    coach_name: Optional[str] = None
    logo: Optional[str] = None
    sponsor_preference: Optional[list[str]] = None


# --------------------------------------------------------------------------- #
# Patrocinadores y recompensas
# --------------------------------------------------------------------------- #
class SponsorPublic(BaseModel):
    id: int
    code: str
    name: str
    metric: str
    description: str
    benefit: str


class SponsorAssignment(BaseModel):
    sponsor_code: str
    sponsor_name: str
    team_id: Optional[int]
    team_name: Optional[str]
    metric: str
    metric_value: Optional[float] = None
    reason: str = ""


class BountyPublic(BaseModel):
    id: int
    code: str
    name: str
    description: str
    reward_gold: int


# --------------------------------------------------------------------------- #
# Clasificacion
# --------------------------------------------------------------------------- #
class StandingRow(BaseModel):
    position: int
    team_id: int
    team_name: str
    logo: str
    race: str
    played: int
    wins: int
    draws: int
    losses: int
    points: int
    td_for: int
    td_against: int
    td_diff: int
    cas_for: int
    cas_against: int
    cas_diff: int
    fouls: int
    passes: int
    ctv: int
    sponsor_code: Optional[str] = None
    sponsor_name: Optional[str] = None


class LeagueStatePublic(BaseModel):
    name: str
    current_round: int
    total_rounds: int
    active_bounty: Optional[BountyPublic] = None
    rookie_safety_last_round: int
    sponsors_first_round: int


# --------------------------------------------------------------------------- #
# Partidos
# --------------------------------------------------------------------------- #
class MatchEventPublic(BaseModel):
    id: int
    match_id: int
    team_id: int
    team_name: str
    player_id: Optional[int]
    player_name: Optional[str]
    event_type: EventType
    turn: Optional[int]
    spp_awarded: int
    victim_player_id: Optional[int]
    victim_player_name: Optional[str]
    casualty_result: Optional[CasualtyResult]
    note: str
    created_at: datetime


class InducementPublic(BaseModel):
    id: int
    match_id: int
    team_id: int
    code: str
    name: str
    quantity: int
    unit_cost: int
    total_cost: int


class MatchSummary(BaseModel):
    id: int
    round_number: int
    status: MatchStatus
    home_team_id: int
    away_team_id: int
    home_team_name: str
    away_team_name: str
    home_logo: str
    away_logo: str
    home_td: int
    away_td: int


class MatchDetail(BaseModel):
    id: int
    round_number: int
    status: MatchStatus
    home_team: TeamSummary
    away_team: TeamSummary
    home_td: int
    away_td: int
    home_ctv: Optional[int]
    away_ctv: Optional[int]
    petty_cash_amount: int
    petty_cash_team_id: Optional[int]
    petty_cash_spent: int
    petty_cash_remaining: int
    home_ready: bool
    away_ready: bool
    weather_roll: Optional[int]
    weather: Optional[dict[str, Any]] = None
    prayer_roll: Optional[int]
    prayer: Optional[dict[str, Any]] = None
    prayer_team_id: Optional[int]
    kick_off_roll: Optional[int]
    kick_off: Optional[dict[str, Any]] = None
    bounty: Optional[BountyPublic] = None
    bounty_winner_team_id: Optional[int]
    home_winnings: int
    away_winnings: int
    home_winnings_roll: Optional[int]
    away_winnings_roll: Optional[int]
    home_mvp_player_id: Optional[int]
    away_mvp_player_id: Optional[int]
    inducements: list[InducementPublic]
    events: list[MatchEventPublic]
    home_players: list[PlayerPublic]
    away_players: list[PlayerPublic]
    scoreboard: dict[str, Any] = Field(default_factory=dict)


class ReadyCheckRequest(BaseModel):
    team_id: int
    pin: str


class RollRequest(BaseModel):
    kind: str  # WEATHER | PRAYER | KICK_OFF
    value: Optional[int] = None  # Si se omite, el servidor tira los dados
    team_id: Optional[int] = None  # Equipo beneficiado por la Plegaria a Nuffle


class InducementRequest(BaseModel):
    team_id: int
    code: str
    quantity: int = 1
    unit_cost: Optional[int] = None  # Solo para Jugadores Estrella (coste variable)


class EventRequest(BaseModel):
    team_id: int
    event_type: EventType
    player_id: Optional[int] = None
    turn: Optional[int] = None
    victim_player_id: Optional[int] = None
    casualty_result: Optional[CasualtyResult] = None
    note: str = ""


class CompleteMatchRequest(BaseModel):
    home_mvp_player_id: Optional[int] = None
    away_mvp_player_id: Optional[int] = None
    home_winnings_roll: Optional[int] = None
    away_winnings_roll: Optional[int] = None
    bounty_winner_team_id: Optional[int] = None


class MatchCompletionReport(BaseModel):
    match_id: int
    home_winnings: int
    away_winnings: int
    injuries: list[dict[str, Any]]
    rookie_safety_payouts: list[dict[str, Any]]
    bounty_payout: Optional[dict[str, Any]] = None
    recovered_players: list[dict[str, Any]]
    sponsors: list[SponsorAssignment]


# --------------------------------------------------------------------------- #
# Roster / mejoras
# --------------------------------------------------------------------------- #
class AdvancementRequest(BaseModel):
    code: str
    skill: Optional[str] = None
    stat: Optional[str] = None


class HirePlayerRequest(BaseModel):
    position_code: str
    name: str
    number: Optional[int] = None


class StaffPurchaseRequest(BaseModel):
    item: str  # REROLL | ASSISTANT_COACH | CHEERLEADER | APOTHECARY | FAN
    quantity: int = 1


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
class AdminMatchStatusRequest(BaseModel):
    status: MatchStatus


class AdminScoreRequest(BaseModel):
    home_td: Optional[int] = None
    away_td: Optional[int] = None


class AdminTreasuryRequest(BaseModel):
    delta: int
    reason: str = ""


class AdminPlayerRequest(BaseModel):
    status: Optional[PlayerStatus] = None
    spp: Optional[int] = None
    current_value: Optional[int] = None
    ma: Optional[int] = None
    st: Optional[int] = None
    ag: Optional[int] = None
    pa: Optional[int] = None
    av: Optional[int] = None


class AdminLeagueStateRequest(BaseModel):
    current_round: Optional[int] = None
    total_rounds: Optional[int] = None
    active_bounty_id: Optional[int] = None


class AdminSponsorOverrideRequest(BaseModel):
    sponsor_code: str
    team_id: Optional[int] = None


TeamSummary.model_rebuild()
TeamDetail.model_rebuild()
