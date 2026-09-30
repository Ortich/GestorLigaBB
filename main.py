import os
import json
import random
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from database import engine, get_session, create_db_and_tables
from models import Team, Player, Match, MatchEvent, LeagueState
from league_engine import (
    calculate_ctv,
    calculate_petty_cash,
    calculate_mercy_rule_compensation,
    calculate_standings,
    assign_dynamic_sponsors
)

# Load rules.json
RULES_PATH = Path(__file__).parent / "rules.json"
with open(RULES_PATH, "r", encoding="utf-8") as f:
    RULES_DATA = json.load(f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(
    title="Blood Bowl BB2020 League Manager API",
    version="1.0.0",
    description="Backend API para la gestión de ligas Blood Bowl BB2020 y asistente de partidos a pie de mesa.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- PYDANTIC SCHEMAS -----------------

class LoginRequest(BaseModel):
    team_id: int
    pin: str

class AdminLoginRequest(BaseModel):
    master_key: str

class ReadyCheckRequest(BaseModel):
    team_id: int
    pin: str

class IncentiveItem(BaseModel):
    id: str
    name: str
    cost: int
    qty: int

class IncentivesRequest(BaseModel):
    team_id: int
    incentives: List[IncentiveItem]

class RollRequest(BaseModel):
    roll_type: str # "weather", "prayers", "kick_off"
    roll_value: Optional[int] = None

class TurnUpdateRequest(BaseModel):
    turn: int
    half: int

class MatchEventCreate(BaseModel):
    team_id: int
    player_id: Optional[int] = None
    event_type: str # "TD", "CAS", "FOUL", "PASS", "INT", "MVP"
    turn: int = 1
    half: int = 1
    details: Optional[str] = None

class CasualtyReport(BaseModel):
    player_id: int
    outcome: str # "MNG", "DEAD"
    injury: Optional[str] = None

class MatchCompleteRequest(BaseModel):
    home_winnings_roll: Optional[int] = None # 1d6
    away_winnings_roll: Optional[int] = None # 1d6
    mvp_player_id_home: Optional[int] = None
    mvp_player_id_away: Optional[int] = None
    casualties: Optional[List[CasualtyReport]] = []

class ForceStatusRequest(BaseModel):
    status: str

class UpdateScoreRequest(BaseModel):
    home_td: int
    away_td: int

class UpdateTreasuryRequest(BaseModel):
    amount: int # Can be positive or negative

class UpdatePlayerStatusRequest(BaseModel):
    status: str # "ACTIVE", "MNG", "DEAD"
    injuries: Optional[str] = None
    spp_delta: Optional[int] = 0

class PlayerCreateRequest(BaseModel):
    name: str
    number: int
    position: str
    ma: int
    st: int
    ag: str
    pa: str
    av: str
    skills: str = ""
    cost: int

class AdvanceRoundRequest(BaseModel):
    round_number: Optional[int] = None
    active_bounty_id: Optional[str] = None

# ----------------- HELPER FUNCTIONS -----------------

def verify_admin(x_master_key: Optional[str] = Header(None), session: Session = Depends(get_session)):
    league = session.exec(select(LeagueState)).first()
    master = league.master_key if league else "bbmaster2026"
    if not x_master_key or x_master_key != master:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave de Comisionado (MASTER_KEY) inválida o ausente."
        )
    return True

# ----------------- ENDPOINTS -----------------

@app.get("/api/rules")
def get_rules():
    """Retorna las tablas oficiales de Clima, Patada Inicial, Plegarias e Incentivos."""
    return RULES_DATA

@app.get("/api/league")
def get_league_info(session: Session = Depends(get_session)):
    """Retorna el estado global de la liga, clasificación completa y sponsors."""
    league = session.exec(select(LeagueState)).first()
    if not league:
        league = LeagueState(id=1, current_round=1, total_rounds=7)
        session.add(league)
        session.commit()
        session.refresh(league)
        
    standings = calculate_standings(session)
    teams = session.exec(select(Team)).all()
    sponsors_summary = {
        t.id: {
            "team_id": t.id,
            "team_name": t.name,
            "sponsor": t.current_sponsor_id,
            "sponsor_info": RULES_DATA["sponsors"].get(t.current_sponsor_id) if t.current_sponsor_id else None
        }
        for t in teams if t.current_sponsor_id
    }
    
    return {
        "league_name": league.league_name,
        "current_round": league.current_round,
        "total_rounds": league.total_rounds,
        "active_bounty_id": league.active_bounty_id,
        "standings": standings,
        "sponsors": sponsors_summary
    }

# --- AUTH ---

@app.post("/api/auth/login")
def login_team(payload: LoginRequest, session: Session = Depends(get_session)):
    team = session.get(Team, payload.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    if team.pin != payload.pin:
        raise HTTPException(status_code=400, detail="PIN incorrecto. Acceso denegado.")
    return {
        "success": True,
        "team_id": team.id,
        "team_name": team.name,
        "coach_name": team.coach_name,
        "race": team.race,
        "role": "coach"
    }

@app.post("/api/auth/admin")
def login_admin(payload: AdminLoginRequest, session: Session = Depends(get_session)):
    league = session.exec(select(LeagueState)).first()
    master = league.master_key if league else "bbmaster2026"
    if payload.master_key != master:
        raise HTTPException(status_code=400, detail="MASTER_KEY inválida.")
    return {
        "success": True,
        "role": "admin",
        "message": "Autenticación de comisionado concedida."
    }

# --- TEAMS & ROSTERS ---

@app.get("/api/teams")
def list_teams(session: Session = Depends(get_session)):
    teams = session.exec(select(Team)).all()
    result = []
    for t in teams:
        players = session.exec(select(Player).where(Player.team_id == t.id)).all()
        ctv = calculate_ctv(t, players)
        active_count = sum(1 for p in players if p.status == "ACTIVE")
        result.append({
            "id": t.id,
            "name": t.name,
            "coach_name": t.coach_name,
            "race": t.race,
            "treasury": t.treasury,
            "rerolls": t.rerolls,
            "reroll_cost": t.reroll_cost,
            "assistant_coaches": t.assistant_coaches,
            "cheerleaders": t.cheerleaders,
            "apothecary": t.apothecary,
            "fans": t.fans,
            "current_sponsor_id": t.current_sponsor_id,
            "ctv": ctv,
            "total_players": len(players),
            "active_players": active_count
        })
    return result

@app.get("/api/teams/{team_id}")
def get_team_detail(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    players = session.exec(select(Player).where(Player.team_id == team.id).order_by(Player.number)).all()
    ctv = calculate_ctv(team, players)
    
    sponsor_info = RULES_DATA["sponsors"].get(team.current_sponsor_id) if team.current_sponsor_id else None

    return {
        "team": {
            "id": team.id,
            "name": team.name,
            "coach_name": team.coach_name,
            "race": team.race,
            "treasury": team.treasury,
            "rerolls": team.rerolls,
            "reroll_cost": team.reroll_cost,
            "assistant_coaches": team.assistant_coaches,
            "cheerleaders": team.cheerleaders,
            "apothecary": team.apothecary,
            "fans": team.fans,
            "current_sponsor_id": team.current_sponsor_id,
            "current_sponsor": sponsor_info,
            "ctv": ctv
        },
        "players": [p.model_dump() for p in players]
    }

@app.post("/api/teams/{team_id}/players")
def hire_player(team_id: int, payload: PlayerCreateRequest, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    if team.treasury < payload.cost:
        raise HTTPException(status_code=400, detail="Fondos insuficientes en la tesorería para contratar al jugador.")
    
    team.treasury -= payload.cost
    session.add(team)
    
    player = Player(
        team_id=team.id,
        name=payload.name,
        number=payload.number,
        position=payload.position,
        ma=payload.ma,
        st=payload.st,
        ag=payload.ag,
        pa=payload.pa,
        av=payload.av,
        skills=payload.skills,
        cost=payload.cost,
        current_value=payload.cost,
        spp=0,
        status="ACTIVE"
    )
    session.add(player)
    session.commit()
    session.refresh(player)
    return player

@app.delete("/api/players/{player_id}")
def fire_player(player_id: int, session: Session = Depends(get_session)):
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado.")
    session.delete(player)
    session.commit()
    return {"success": True, "message": "Jugador despedido de la plantilla."}

# --- MATCHES & ASSISTANT FLOW ---

@app.get("/api/matches")
def list_matches(round_number: Optional[int] = None, team_id: Optional[int] = None, session: Session = Depends(get_session)):
    query = select(Match)
    if round_number:
        query = query.where(Match.round_number == round_number)
    if team_id:
        query = query.where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
    matches = session.exec(query.order_by(Match.round_number, Match.id)).all()
    
    teams = {t.id: t for t in session.exec(select(Team)).all()}
    
    result = []
    for m in matches:
        home_team = teams.get(m.home_team_id)
        away_team = teams.get(m.away_team_id)
        result.append({
            "id": m.id,
            "round_number": m.round_number,
            "status": m.status,
            "home_team_id": m.home_team_id,
            "home_team_name": home_team.name if home_team else "Unknown",
            "home_race": home_team.race if home_team else "",
            "away_team_id": m.away_team_id,
            "away_team_name": away_team.name if away_team else "Unknown",
            "away_race": away_team.race if away_team else "",
            "home_td": m.home_td,
            "away_td": m.away_td,
            "home_ctv": m.home_ctv,
            "away_ctv": m.away_ctv,
            "petty_cash_amount": m.petty_cash_amount,
            "weather_name": m.weather_name,
            "home_coach_ready": m.home_coach_ready,
            "away_coach_ready": m.away_coach_ready
        })
    return result

@app.get("/api/matches/{match_id}")
def get_match_detail(match_id: int, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
        
    home_team = session.get(Team, match.home_team_id)
    away_team = session.get(Team, match.away_team_id)
    
    home_players = session.exec(select(Player).where(Player.team_id == match.home_team_id).order_by(Player.number)).all()
    away_players = session.exec(select(Player).where(Player.team_id == match.away_team_id).order_by(Player.number)).all()
    
    # Calculate live CTVs
    home_ctv = calculate_ctv(home_team, home_players) if home_team else 0
    away_ctv = calculate_ctv(away_team, away_players) if away_team else 0
    petty_calc = calculate_petty_cash(home_ctv, away_ctv)
    
    # Fetch events
    events = session.exec(select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.id.desc())).all()
    
    # Deserialize incentives
    try:
        home_inc = json.loads(match.home_incentives)
    except Exception:
        home_inc = []
    try:
        away_inc = json.loads(match.away_incentives)
    except Exception:
        away_inc = []
        
    return {
        "match": match.model_dump(),
        "home_team": home_team.model_dump() if home_team else None,
        "away_team": away_team.model_dump() if away_team else None,
        "home_players": [p.model_dump() for p in home_players],
        "away_players": [p.model_dump() for p in away_players],
        "calculated_home_ctv": home_ctv,
        "calculated_away_ctv": away_ctv,
        "petty_cash_info": petty_calc,
        "home_incentives": home_inc,
        "away_incentives": away_inc,
        "events": [e.model_dump() for e in events]
    }

@app.post("/api/matches/{match_id}/ready-check")
def match_ready_check(match_id: int, payload: ReadyCheckRequest, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status not in ["SCHEDULED", "READY_CHECK"]:
        raise HTTPException(status_code=400, detail=f"No se puede realizar el Ready Check en estado {match.status}.")

    team = session.get(Team, payload.team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    if team.pin != payload.pin:
        raise HTTPException(status_code=400, detail="PIN incorrecto para este equipo.")

    match.status = "READY_CHECK"
    if payload.team_id == match.home_team_id:
        match.home_coach_ready = True
    elif payload.team_id == match.away_team_id:
        match.away_coach_ready = True
    else:
        raise HTTPException(status_code=400, detail="El equipo indicado no participa en este partido.")

    # If both coaches are ready, compute CTVs and transition to PRE_MATCH
    if match.home_coach_ready and match.away_coach_ready:
        match.status = "PRE_MATCH"
        home_team = session.get(Team, match.home_team_id)
        away_team = session.get(Team, match.away_team_id)
        home_players = session.exec(select(Player).where(Player.team_id == match.home_team_id)).all()
        away_players = session.exec(select(Player).where(Player.team_id == match.away_team_id)).all()
        
        match.home_ctv = calculate_ctv(home_team, home_players)
        match.away_ctv = calculate_ctv(away_team, away_players)
        petty_info = calculate_petty_cash(match.home_ctv, match.away_ctv)
        
        match.petty_cash_amount = petty_info["amount"]
        if petty_info["beneficiary"] == "home":
            match.petty_cash_team_id = match.home_team_id
        elif petty_info["beneficiary"] == "away":
            match.petty_cash_team_id = match.away_team_id
        else:
            match.petty_cash_team_id = None

    session.add(match)
    session.commit()
    session.refresh(match)
    return {
        "success": True,
        "match_status": match.status,
        "home_coach_ready": match.home_coach_ready,
        "away_coach_ready": match.away_coach_ready,
        "home_ctv": match.home_ctv,
        "away_ctv": match.away_ctv,
        "petty_cash_amount": match.petty_cash_amount,
        "petty_cash_team_id": match.petty_cash_team_id
    }

@app.post("/api/matches/{match_id}/incentives")
def buy_incentives(match_id: int, payload: IncentivesRequest, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status != "PRE_MATCH":
        raise HTTPException(status_code=400, detail="Los incentivos sólo pueden comprarse durante la fase PRE_MATCH.")

    total_spent = sum(item.cost * item.qty for item in payload.incentives)
    
    # Check petty cash constraint
    if payload.team_id == match.petty_cash_team_id:
        if total_spent > match.petty_cash_amount:
            raise HTTPException(
                status_code=400,
                detail=f"El total gastado ({total_spent} po) supera el Petty Cash disponible ({match.petty_cash_amount} po)."
            )
    else:
        # Team is not petty cash beneficiary. Blood Bowl rules:
        # "El equipo de menor VAE NO puede gastar oro de su propia tesorería para superar a su rival. El crédito no gastado se pierde."
        # If higher VAE team wants incentives, they'd pay from treasury, but user prompt states:
        # "El equipo con MENOR VAE recibe una cantidad exacta de oro igual a la diferencia que solo puede usar en ese partido para comprar incentivos... El crédito no gastado se pierde."
        team = session.get(Team, payload.team_id)
        if total_spent > team.treasury:
            raise HTTPException(status_code=400, detail="Tesorería insuficiente para comprar incentivos adicionales.")
        # Note: we don't deduct petty cash from treasury since petty cash is granted for the match
        
    inc_json = json.dumps([item.model_dump() for item in payload.incentives])
    if payload.team_id == match.home_team_id:
        match.home_incentives = inc_json
        match.home_petty_spent = total_spent
    elif payload.team_id == match.away_team_id:
        match.away_incentives = inc_json
        match.away_petty_spent = total_spent
    else:
        raise HTTPException(status_code=400, detail="Equipo no válido para este partido.")

    session.add(match)
    session.commit()
    session.refresh(match)
    return {"success": True, "spent": total_spent, "incentives": payload.incentives}

@app.post("/api/matches/{match_id}/roll")
def execute_roll(match_id: int, payload: RollRequest, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status not in ["PRE_MATCH", "IN_PROGRESS"]:
        raise HTTPException(status_code=400, detail="Tiradas sólo permitidas en PRE_MATCH o IN_PROGRESS.")

    roll_type = payload.roll_type
    
    if roll_type == "weather":
        # 2d6 (2-12)
        val = payload.roll_value if payload.roll_value is not None else (random.randint(1, 6) + random.randint(1, 6))
        rule = RULES_DATA["weather_table"].get(str(val), {"name": "Clima", "description": ""})
        match.weather_roll = val
        match.weather_name = rule["name"]
        match.weather_description = rule["description"]
    elif roll_type == "kick_off":
        # 2d6 (2-12)
        val = payload.roll_value if payload.roll_value is not None else (random.randint(1, 6) + random.randint(1, 6))
        rule = RULES_DATA["kick_off_table"].get(str(val), {"name": "Patada Inicial", "description": ""})
        match.kick_off_roll = val
        match.kick_off_name = rule["name"]
        match.kick_off_description = rule["description"]
    elif roll_type == "prayers":
        # 1d16 (1-16)
        val = payload.roll_value if payload.roll_value is not None else random.randint(1, 16)
        rule = RULES_DATA["prayers_to_nuffle"].get(str(val), {"name": "Plegaria a Nuffle", "description": ""})
        match.prayers_roll = val
        match.prayers_name = rule["name"]
        match.prayers_description = rule["description"]
    else:
        raise HTTPException(status_code=400, detail=f"Tipo de tirada desconocido: {roll_type}")

    session.add(match)
    session.commit()
    session.refresh(match)
    return {
        "success": True,
        "roll_type": roll_type,
        "roll_value": val,
        "name": getattr(match, f"{roll_type}_name", ""),
        "description": getattr(match, f"{roll_type}_description", "")
    }

@app.post("/api/matches/{match_id}/start")
def start_match(match_id: int, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status != "PRE_MATCH":
        raise HTTPException(status_code=400, detail="El partido debe estar en fase PRE_MATCH para iniciarse.")

    match.status = "IN_PROGRESS"
    match.current_turn = 1
    match.current_half = 1
    session.add(match)
    session.commit()
    session.refresh(match)
    return {"success": True, "status": match.status}

@app.post("/api/matches/{match_id}/turn")
def update_turn(match_id: int, payload: TurnUpdateRequest, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    match.current_turn = payload.turn
    match.current_half = payload.half
    session.add(match)
    session.commit()
    return {"success": True, "turn": match.current_turn, "half": match.current_half}

@app.post("/api/matches/{match_id}/events")
def add_match_event(match_id: int, payload: MatchEventCreate, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status not in ["IN_PROGRESS", "COMPLETED"]:
        raise HTTPException(status_code=400, detail="Sólo se pueden registrar eventos en partidos IN_PROGRESS o COMPLETED.")

    # Create event
    event = MatchEvent(
        match_id=match.id,
        team_id=payload.team_id,
        player_id=payload.player_id,
        event_type=payload.event_type,
        turn=payload.turn,
        half=payload.half,
        details=payload.details
    )
    session.add(event)
    
    # Update score if TD
    if payload.event_type == "TD":
        if payload.team_id == match.home_team_id:
            match.home_td += 1
        elif payload.team_id == match.away_team_id:
            match.away_td += 1
        session.add(match)

    # Award SPP automatically to player
    spp_gain = 0
    if payload.player_id:
        player = session.get(Player, payload.player_id)
        if player:
            if payload.event_type == "TD":
                spp_gain = 3
            elif payload.event_type == "CAS":
                spp_gain = 2
            elif payload.event_type == "PASS":
                spp_gain = 1
            elif payload.event_type == "INT":
                spp_gain = 2
            elif payload.event_type == "MVP":
                spp_gain = 4
            
            player.spp += spp_gain
            session.add(player)

    session.commit()
    session.refresh(event)
    session.refresh(match)
    return {
        "success": True,
        "event": event.model_dump(),
        "home_td": match.home_td,
        "away_td": match.away_td,
        "spp_awarded": spp_gain
    }

@app.delete("/api/matches/{match_id}/events/{event_id}")
def delete_match_event(match_id: int, event_id: int, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    event = session.get(MatchEvent, event_id)
    if not match or not event or event.match_id != match.id:
        raise HTTPException(status_code=404, detail="Evento o partido no encontrado.")

    # Revert score if TD
    if event.event_type == "TD":
        if event.team_id == match.home_team_id and match.home_td > 0:
            match.home_td -= 1
        elif event.team_id == match.away_team_id and match.away_td > 0:
            match.away_td -= 1
        session.add(match)

    # Revert SPP
    if event.player_id:
        player = session.get(Player, event.player_id)
        if player:
            spp_loss = 0
            if event.event_type == "TD":
                spp_loss = 3
            elif event.event_type == "CAS":
                spp_loss = 2
            elif event.event_type == "PASS":
                spp_loss = 1
            elif event.event_type == "INT":
                spp_loss = 2
            elif event.event_type == "MVP":
                spp_loss = 4
            player.spp = max(0, player.spp - spp_loss)
            session.add(player)

    session.delete(event)
    session.commit()
    session.refresh(match)
    return {"success": True, "home_td": match.home_td, "away_td": match.away_td}

@app.post("/api/matches/{match_id}/complete")
def complete_match(match_id: int, payload: MatchCompleteRequest, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    if match.status not in ["IN_PROGRESS", "READY_CHECK", "PRE_MATCH", "SCHEDULED"]:
        raise HTTPException(status_code=400, detail="El partido ya está completado.")

    home_team = session.get(Team, match.home_team_id)
    away_team = session.get(Team, match.away_team_id)

    # 1. Winnings roll: (1d6 * 10,000) for each team
    home_w_roll = payload.home_winnings_roll if payload.home_winnings_roll is not None else random.randint(1, 6)
    away_w_roll = payload.away_winnings_roll if payload.away_winnings_roll is not None else random.randint(1, 6)

    home_winnings = home_w_roll * 10_000
    away_winnings = away_w_roll * 10_000

    # Sponsor bonus check: Carnicería Da Boyz (+20k if team inflicted >= 2 CAS)
    home_cas_count = len(session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id, MatchEvent.team_id == match.home_team_id, MatchEvent.event_type == "CAS")
    ).all())
    away_cas_count = len(session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id, MatchEvent.team_id == match.away_team_id, MatchEvent.event_type == "CAS")
    ).all())

    if home_team.current_sponsor_id == "carniceria_da_boyz" and home_cas_count >= 2:
        home_winnings += 20_000
    if away_team.current_sponsor_id == "carniceria_da_boyz" and away_cas_count >= 2:
        away_winnings += 20_000

    home_team.treasury += home_winnings
    away_team.treasury += away_winnings
    match.home_winnings = home_winnings
    match.away_winnings = away_winnings

    # 2. Award MVP (+4 SPP each)
    if payload.mvp_player_id_home:
        match.mvp_player_id_home = payload.mvp_player_id_home
        p_home = session.get(Player, payload.mvp_player_id_home)
        if p_home:
            p_home.spp += 4
            session.add(p_home)
            session.add(MatchEvent(
                match_id=match.id,
                team_id=match.home_team_id,
                player_id=p_home.id,
                event_type="MVP",
                turn=8,
                half=2,
                details="MVP del partido para el equipo local (+4 SPP)"
            ))

    if payload.mvp_player_id_away:
        match.mvp_player_id_away = payload.mvp_player_id_away
        p_away = session.get(Player, payload.mvp_player_id_away)
        if p_away:
            p_away.spp += 4
            session.add(p_away)
            session.add(MatchEvent(
                match_id=match.id,
                team_id=match.away_team_id,
                player_id=p_away.id,
                event_type="MVP",
                turn=8,
                half=2,
                details="MVP del partido para el equipo visitante (+4 SPP)"
            ))

    # 3. Process Casualties and Mercy Rule
    # Count prior fatalities of the teams to know which tier of mercy rule applies
    mercy_details = []
    if payload.casualties:
        for cas in payload.casualties:
            player = session.get(Player, cas.player_id)
            if not player:
                continue
            player.status = cas.outcome # "MNG" or "DEAD"
            if cas.injury:
                player.injuries = f"{player.injuries}, {cas.injury}".strip(", ")
            session.add(player)

            # Mercy Rule Check: only if round <= 2 and outcome is DEAD or permanent injury
            if match.round_number <= 2 and cas.outcome in ["DEAD", "MNG"]:
                team = session.get(Team, player.team_id)
                # Count prior dead/fatalities for this team
                dead_players_count = len(session.exec(
                    select(Player).where(Player.team_id == player.team_id, Player.status == "DEAD")
                ).all())
                comp = calculate_mercy_rule_compensation(match.round_number, dead_players_count, player.cost)
                if comp > 0 and team:
                    team.treasury += comp
                    session.add(team)
                    mercy_details.append({
                        "team_name": team.name,
                        "player_name": player.name,
                        "compensation": comp,
                        "reason": f"Red de Seguridad de Novatos (Jornada {match.round_number})"
                    })

    match.status = "COMPLETED"
    session.add(match)
    session.add(home_team)
    session.add(away_team)
    session.commit()
    session.refresh(match)

    # Check if sponsors should be assigned (Round >= 3)
    league = session.exec(select(LeagueState)).first()
    curr_round = league.current_round if league else match.round_number
    sponsors = assign_dynamic_sponsors(session, current_round=curr_round)

    return {
        "success": True,
        "match_id": match.id,
        "status": match.status,
        "home_winnings": home_winnings,
        "away_winnings": away_winnings,
        "mercy_rule_compensations": mercy_details,
        "sponsors_updated": sponsors
    }

# --- COMMISSIONER / ADMIN PANEL ---

@app.post("/api/admin/matches/{match_id}/force-status")
def admin_force_status(
    match_id: int,
    payload: ForceStatusRequest,
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    match.status = payload.status
    session.add(match)
    session.commit()
    session.refresh(match)
    return {"success": True, "match_id": match.id, "new_status": match.status}

@app.post("/api/admin/matches/{match_id}/update-score")
def admin_update_score(
    match_id: int,
    payload: UpdateScoreRequest,
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    match = session.get(Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado.")
    match.home_td = payload.home_td
    match.away_td = payload.away_td
    session.add(match)
    session.commit()
    session.refresh(match)
    return {"success": True, "home_td": match.home_td, "away_td": match.away_td}

@app.post("/api/admin/teams/{team_id}/treasury")
def admin_update_treasury(
    team_id: int,
    payload: UpdateTreasuryRequest,
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado.")
    team.treasury = max(0, team.treasury + payload.amount)
    session.add(team)
    session.commit()
    session.refresh(team)
    return {"success": True, "team_id": team.id, "new_treasury": team.treasury}

@app.post("/api/admin/players/{player_id}/status")
def admin_update_player_status(
    player_id: int,
    payload: UpdatePlayerStatusRequest,
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    player = session.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado.")
    player.status = payload.status
    if payload.injuries is not None:
        player.injuries = payload.injuries
    if payload.spp_delta:
        player.spp = max(0, player.spp + payload.spp_delta)
    session.add(player)
    session.commit()
    session.refresh(player)
    return {"success": True, "player": player.model_dump()}

@app.post("/api/admin/recalculate")
def admin_recalculate(
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    """Botón de peligro: recalcula standings y reasigna sponsors desde cero."""
    league = session.exec(select(LeagueState)).first()
    curr_round = league.current_round if league else 1
    standings = calculate_standings(session)
    sponsors = assign_dynamic_sponsors(session, current_round=curr_round)
    return {
        "success": True,
        "message": "Clasificación y sponsors recalculados con éxito.",
        "standings": standings,
        "sponsors": sponsors
    }

@app.post("/api/admin/league/advance-round")
def admin_advance_round(
    payload: AdvanceRoundRequest,
    is_admin: bool = Depends(verify_admin),
    session: Session = Depends(get_session)
):
    league = session.exec(select(LeagueState)).first()
    if not league:
        league = LeagueState(id=1, current_round=1, total_rounds=7)
    if payload.round_number:
        league.current_round = payload.round_number
    else:
        league.current_round += 1
    if payload.active_bounty_id is not None:
        league.active_bounty_id = payload.active_bounty_id
    session.add(league)
    session.commit()
    session.refresh(league)
    
    # Reassign sponsors for new round if >= 3
    sponsors = assign_dynamic_sponsors(session, current_round=league.current_round)
    return {
        "success": True,
        "current_round": league.current_round,
        "active_bounty_id": league.active_bounty_id,
        "sponsors": sponsors
    }

# Mount static build if available
STATIC_DIR = Path(__file__).parent / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    def serve_root():
        return FileResponse(STATIC_DIR / "index.html")
    
    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
