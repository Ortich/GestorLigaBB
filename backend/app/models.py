"""Modelos SQLModel de la liga (FASE 1).

Esquema relacional completo: equipos, jugadores, partidos, eventos de partido,
incentivos comprados, patrocinadores, recompensas semanales y estado de liga.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- #
# Enumeraciones
# --------------------------------------------------------------------------- #
class PlayerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    MNG = "MNG"  # Miss Next Game
    DEAD = "DEAD"
    RETIRED = "RETIRED"


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    READY_CHECK = "READY_CHECK"
    PRE_MATCH = "PRE_MATCH"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class EventType(str, Enum):
    TD = "TD"
    CAS = "CAS"
    FOUL = "FOUL"
    PASS = "PASS"  # Pase completado
    INT = "INT"  # Intercepcion
    DEFLECTION = "DEFLECTION"
    MVP = "MVP"


class CasualtyResult(str, Enum):
    """Resultado de la tirada de heridas (BB2020)."""

    BADLY_HURT = "BADLY_HURT"
    SERIOUSLY_HURT = "SERIOUSLY_HURT"
    SERIOUS_INJURY = "SERIOUS_INJURY"
    LASTING_INJURY_MA = "LASTING_INJURY_MA"
    LASTING_INJURY_ST = "LASTING_INJURY_ST"
    LASTING_INJURY_AG = "LASTING_INJURY_AG"
    LASTING_INJURY_PA = "LASTING_INJURY_PA"
    LASTING_INJURY_AV = "LASTING_INJURY_AV"
    DEAD = "DEAD"


#: Resultados que dejan al jugador fuera del proximo partido.
MNG_RESULTS = {
    CasualtyResult.SERIOUSLY_HURT,
    CasualtyResult.SERIOUS_INJURY,
    CasualtyResult.LASTING_INJURY_MA,
    CasualtyResult.LASTING_INJURY_ST,
    CasualtyResult.LASTING_INJURY_AG,
    CasualtyResult.LASTING_INJURY_PA,
    CasualtyResult.LASTING_INJURY_AV,
}

#: Resultados considerados "baja permanente" para la Red de Seguridad de Novatos.
PERMANENT_RESULTS = {
    CasualtyResult.LASTING_INJURY_MA,
    CasualtyResult.LASTING_INJURY_ST,
    CasualtyResult.LASTING_INJURY_AG,
    CasualtyResult.LASTING_INJURY_PA,
    CasualtyResult.LASTING_INJURY_AV,
    CasualtyResult.DEAD,
}

#: Caracteristica degradada por cada lesion persistente.
LASTING_INJURY_STAT = {
    CasualtyResult.LASTING_INJURY_MA: "ma",
    CasualtyResult.LASTING_INJURY_ST: "st",
    CasualtyResult.LASTING_INJURY_AG: "ag",
    CasualtyResult.LASTING_INJURY_PA: "pa",
    CasualtyResult.LASTING_INJURY_AV: "av",
}


class InducementFunding(str, Enum):
    PETTY_CASH = "PETTY_CASH"
    TREASURY = "TREASURY"


# --------------------------------------------------------------------------- #
# Tablas
# --------------------------------------------------------------------------- #
class Sponsor(SQLModel, table=True):
    """Patrocinador dinamico (mecanica de catch-up)."""

    __tablename__ = "sponsor"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    metric: str  # LAST_IN_TABLE | WORST_TD_DIFF | MOST_CAS | MOST_FOULS
    description: str = ""
    benefit: str = ""
    priority: int = 0  # Orden por defecto para resolver colisiones


class Bounty(SQLModel, table=True):
    """Recompensa semanal activa en la liga."""

    __tablename__ = "bounty"

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    description: str = ""
    reward_gold: int = 0


class Team(SQLModel, table=True):
    __tablename__ = "team"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    coach_name: str
    race: str
    pin_hash: str = ""
    treasury: int = 0
    rerolls: int = 0
    reroll_cost: int = 50_000
    assistant_coaches: int = 0
    cheerleaders: int = 0
    apothecary: bool = False
    fans: int = 1  # Hinchas dedicados: no suman a la VAE. Siempre entre 1 y 7.
    current_sponsor_id: Optional[int] = Field(default=None, foreign_key="sponsor.id")
    sponsor_preference: str = ""  # Codigos separados por coma, para resolver colisiones
    rookie_safety_claims: int = 0  # Bajas permanentes ya compensadas (Mercy Rule)
    logo: str = "\U0001f6e1"
    created_at: datetime = Field(default_factory=utcnow)

    players: List["Player"] = Relationship(
        back_populates="team",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    @field_validator("fans")
    @classmethod
    def _hinchas_entre_1_y_7(cls, value: int) -> int:
        if value < 1 or value > 7:
            raise ValueError("Los hinchas dedicados tienen que estar entre 1 y 7.")
        return value


class Player(SQLModel, table=True):
    __tablename__ = "player"

    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    number: int = 1
    name: str
    position: str
    ma: int = 6
    st: int = 3
    ag: int = 3
    pa: Optional[int] = 4
    av: int = 9
    skills: str = ""  # Lista separada por comas
    cost: int = 0  # Coste de contratacion original
    current_value: int = 0  # Valor actual (coste + mejoras)
    spp: int = 0
    status: PlayerStatus = Field(default=PlayerStatus.ACTIVE, index=True)
    # Sin ForeignKey a proposito: match ya referencia a player (MVP) y SQLite no
    # sabe ordenar el DROP de un ciclo de claves foraneas.
    mng_match_id: Optional[int] = None
    niggling_injuries: int = 0
    journeyman: bool = False

    team: Optional[Team] = Relationship(back_populates="players")


class Match(SQLModel, table=True):
    __tablename__ = "match"

    id: Optional[int] = Field(default=None, primary_key=True)
    round_number: int = Field(index=True)
    home_team_id: int = Field(foreign_key="team.id", index=True)
    away_team_id: int = Field(foreign_key="team.id", index=True)
    status: MatchStatus = Field(default=MatchStatus.SCHEDULED, index=True)

    home_td: int = 0
    away_td: int = 0

    # Snapshot de VAE tomado al entrar en PRE_MATCH
    home_ctv: Optional[int] = None
    away_ctv: Optional[int] = None
    petty_cash_amount: int = 0
    petty_cash_team_id: Optional[int] = Field(default=None, foreign_key="team.id")

    # Ready check
    home_ready: bool = False
    away_ready: bool = False

    # Tiradas de prepartido
    weather_roll: Optional[int] = None
    weather_result: Optional[str] = None
    prayer_roll: Optional[int] = None
    prayer_result: Optional[str] = None
    prayer_team_id: Optional[int] = Field(default=None, foreign_key="team.id")
    kick_off_roll: Optional[int] = None
    kick_off_result: Optional[str] = None

    # Recompensa semanal
    bounty_id: Optional[int] = Field(default=None, foreign_key="bounty.id")
    bounty_winner_team_id: Optional[int] = Field(default=None, foreign_key="team.id")

    # Postpartido
    home_winnings_roll: Optional[int] = None
    away_winnings_roll: Optional[int] = None
    home_winnings: int = 0
    away_winnings: int = 0
    home_fans_roll: Optional[int] = None
    away_fans_roll: Optional[int] = None
    home_fans_before: Optional[int] = None
    away_fans_before: Optional[int] = None
    home_fans_after: Optional[int] = None
    away_fans_after: Optional[int] = None
    home_gold_discarded: int = 0
    away_gold_discarded: int = 0
    conceded_by_team_id: Optional[int] = Field(default=None, foreign_key="team.id")
    home_mvp_player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    away_mvp_player_id: Optional[int] = Field(default=None, foreign_key="player.id")

    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MatchEvent(SQLModel, table=True):
    __tablename__ = "matchevent"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    event_type: EventType = Field(index=True)
    turn: Optional[int] = None
    spp_awarded: int = 0
    # Solo para CAS: victima y resultado de la tirada de heridas
    victim_player_id: Optional[int] = Field(default=None, foreign_key="player.id")
    casualty_result: Optional[CasualtyResult] = None
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class MatchInducement(SQLModel, table=True):
    """Incentivo comprado en el prepartido."""

    __tablename__ = "matchinducement"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    team_id: int = Field(foreign_key="team.id", index=True)
    code: str
    name: str
    quantity: int = 1
    unit_cost: int = 0
    total_cost: int = 0
    funding: InducementFunding = InducementFunding.PETTY_CASH


class LeagueState(SQLModel, table=True):
    __tablename__ = "leaguestate"

    id: Optional[int] = Field(default=1, primary_key=True)
    name: str = "Liga Privada Blood Bowl 2020"
    current_round: int = 1
    total_rounds: int = 7
    active_bounty_id: Optional[int] = Field(default=None, foreign_key="bounty.id")
    rookie_safety_last_round: int = 2  # Mercy Rule activa hasta esta jornada
