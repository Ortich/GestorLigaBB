import json
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from models import Team, Player, Match, MatchEvent, LeagueState

def calculate_ctv(team: Team, players: List[Player]) -> int:
    """
    Calculates Current Team Value (VAE / CTV).
    - Sum of value of all ACTIVE players (excluding MNG or DEAD).
    - Plus Rerolls (rerolls * reroll_cost).
    - Plus Assistant Coaches (assistant_coaches * 10,000).
    - Plus Cheerleaders (cheerleaders * 10,000).
    - Plus Apothecary (apothecary * 50,000).
    - Treasury and Dedicated Fans do NOT count towards CTV.
    """
    active_players_value = sum(
        p.current_value for p in players 
        if p.status == "ACTIVE"
    )
    rerolls_value = team.rerolls * team.reroll_cost
    coaches_value = team.assistant_coaches * 10_000
    cheerleaders_value = team.cheerleaders * 10_000
    apothecary_value = (1 if team.apothecary else 0) * 50_000

    return active_players_value + rerolls_value + coaches_value + cheerleaders_value + apothecary_value

def calculate_petty_cash(home_ctv: int, away_ctv: int) -> Dict[str, Any]:
    """
    Compares CTV of both teams. The team with LOWER CTV receives exact difference.
    """
    diff = abs(home_ctv - away_ctv)
    if home_ctv < away_ctv:
        return {
            "beneficiary": "home",
            "amount": diff,
            "higher_ctv": away_ctv,
            "lower_ctv": home_ctv
        }
    elif away_ctv < home_ctv:
        return {
            "beneficiary": "away",
            "amount": diff,
            "higher_ctv": home_ctv,
            "lower_ctv": away_ctv
        }
    else:
        return {
            "beneficiary": None,
            "amount": 0,
            "higher_ctv": home_ctv,
            "lower_ctv": away_ctv
        }

def calculate_mercy_rule_compensation(round_number: int, team_fatalities_count: int, player_cost: int) -> int:
    """
    Red de Seguridad de Novatos (Mercy Rule):
    - Exclusive for Round 1 and Round 2.
    - If a player suffers permanent injury or death:
      * 1st casualty: 100% of player cost
      * 2nd casualty: 50% of player cost
      * 3rd+ casualty: 25% of player cost
    - Returns gold amount to credit to team treasury.
    """
    if round_number > 2:
        return 0
    
    if team_fatalities_count <= 1:
        return player_cost
    elif team_fatalities_count == 2:
        return int(player_cost * 0.5)
    else:
        return int(player_cost * 0.25)

def calculate_standings(session: Session) -> List[Dict[str, Any]]:
    """
    Calculates standings for all teams based on completed matches and events.
    Points:
    - Win: 3 pts
    - Draw: 1 pt
    - Loss by 1 TD: 1 pt
    - Loss by >1 TD: 0 pts
    
    Tiebreakers:
    1º TD Difference (td_diff)
    2º Casualties Difference (cas_diff)
    3º Total TDs scored (td_for)
    """
    teams = session.exec(select(Team)).all()
    matches = session.exec(select(Match).where(Match.status == "COMPLETED")).all()
    events = session.exec(select(MatchEvent)).all()
    
    # Initialize stats dict for each team
    stats = {}
    for team in teams:
        stats[team.id] = {
            "team_id": team.id,
            "team_name": team.name,
            "coach_name": team.coach_name,
            "race": team.race,
            "current_sponsor_id": team.current_sponsor_id,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "pts": 0,
            "td_for": 0,
            "td_against": 0,
            "td_diff": 0,
            "cas_for": 0,
            "cas_against": 0,
            "cas_diff": 0,
            "fouls_committed": 0,
            "passes_completed": 0,
            "interceptions": 0,
        }
        
    # Process completed matches for TDs and Points
    for match in matches:
        h_id = match.home_team_id
        a_id = match.away_team_id
        
        if h_id not in stats or a_id not in stats:
            continue
            
        h_td = match.home_td
        a_td = match.away_td
        
        stats[h_id]["played"] += 1
        stats[a_id]["played"] += 1
        stats[h_id]["td_for"] += h_td
        stats[h_id]["td_against"] += a_td
        stats[a_id]["td_for"] += a_td
        stats[a_id]["td_against"] += h_td
        
        if h_td > a_td:
            # Home wins
            stats[h_id]["won"] += 1
            stats[h_id]["pts"] += 3
            stats[a_id]["lost"] += 1
            if (h_td - a_td) == 1:
                stats[a_id]["pts"] += 1 # Bonus point for losing by 1 TD
        elif a_td > h_td:
            # Away wins
            stats[a_id]["won"] += 1
            stats[a_id]["pts"] += 3
            stats[h_id]["lost"] += 1
            if (a_td - h_td) == 1:
                stats[h_id]["pts"] += 1 # Bonus point for losing by 1 TD
        else:
            # Draw
            stats[h_id]["drawn"] += 1
            stats[a_id]["drawn"] += 1
            stats[h_id]["pts"] += 1
            stats[a_id]["pts"] += 1

    # Map match IDs to home and away teams for events
    match_map = {m.id: m for m in session.exec(select(Match)).all()}
    
    # Process events for casualties, fouls, passes, interceptions
    for ev in events:
        t_id = ev.team_id
        if t_id not in stats:
            continue
            
        m = match_map.get(ev.match_id)
        opp_id = None
        if m:
            opp_id = m.away_team_id if m.home_team_id == t_id else m.home_team_id

        if ev.event_type == "CAS":
            stats[t_id]["cas_for"] += 1
            if opp_id and opp_id in stats:
                stats[opp_id]["cas_against"] += 1
        elif ev.event_type == "FOUL":
            stats[t_id]["fouls_committed"] += 1
        elif ev.event_type == "PASS":
            stats[t_id]["passes_completed"] += 1
        elif ev.event_type == "INT":
            stats[t_id]["interceptions"] += 1

    # Compute differentials
    standings_list = []
    for s in stats.values():
        s["td_diff"] = s["td_for"] - s["td_against"]
        s["cas_diff"] = s["cas_for"] - s["cas_against"]
        standings_list.append(s)
        
    # Sort with tiebreakers:
    # 1. pts DESC
    # 2. td_diff DESC
    # 3. cas_diff DESC
    # 4. td_for DESC
    # 5. team_name ASC
    standings_list.sort(
        key=lambda x: (
            x["pts"],
            x["td_diff"],
            x["cas_diff"],
            x["td_for"],
            -x["team_id"]
        ),
        reverse=True
    )
    
    # Add rank (1-indexed)
    for idx, row in enumerate(standings_list):
        row["rank"] = idx + 1
        
    return standings_list

def assign_dynamic_sponsors(session: Session, current_round: int) -> Dict[str, Optional[int]]:
    """
    Sponsors Dinámicos (Catch-up Mechanic):
    - Evaluated at the end of each round starting from Round 3.
    - Strict assignment of 1 sponsor per team (4 sponsors total, 8 teams).
    - If collision occurs (a team leads multiple metrics):
      Priority of choice: the team lowest on the table picks first.
      The team selects their preferred sponsor (or the one they lead by best margin),
      and the unselected sponsor passes to the next eligible team in that category ranking.
    
    The 4 Sponsors:
    - Prensa Amarilla: Last in standings (lowest rank in table)
    - El Rincón del Tabernero: Worst TD differential (lowest td_diff)
    - Carnicería Da Boyz: Most casualties caused (highest cas_for)
    - Sindicato Malhechores: Most fouls committed (highest fouls_committed)
    """
    standings = calculate_standings(session)
    if not standings:
        return {}
        
    if current_round < 3:
        # Reset any sponsors before round 3
        teams = session.exec(select(Team)).all()
        for t in teams:
            t.current_sponsor_id = None
            session.add(t)
        session.commit()
        return {}

    # Category rankings (ordered by priority for each sponsor)
    # 1. Prensa Amarilla: lowest on the table (highest rank number)
    ranked_prensa = sorted(standings, key=lambda x: (-x["rank"], -x["team_id"]))
    
    # 2. Rincon del Tabernero: lowest td_diff, then lowest standing
    ranked_tabernero = sorted(standings, key=lambda x: (x["td_diff"], -x["rank"]))
    
    # 3. Carniceria Da Boyz: highest cas_for, then lowest standing
    ranked_carniceria = sorted(standings, key=lambda x: (-x["cas_for"], -x["rank"]))
    
    # 4. Sindicato Malhechores: highest fouls_committed, then lowest standing
    ranked_malhechores = sorted(standings, key=lambda x: (-x["fouls_committed"], -x["rank"]))
    
    category_candidates = {
        "prensa_amarilla": [item["team_id"] for item in ranked_prensa],
        "rincon_tabernero": [item["team_id"] for item in ranked_tabernero],
        "carniceria_da_boyz": [item["team_id"] for item in ranked_carniceria],
        "sindicato_malhechores": [item["team_id"] for item in ranked_malhechores],
    }
    
    # Order of teams to choose: lowest in standings first
    teams_by_lowest_rank = sorted(standings, key=lambda x: x["rank"], reverse=True)
    
    assigned_sponsors = {} # sponsor_id -> team_id
    assigned_teams = set() # set of team_ids that already have a sponsor
    
    # Team priority choice algorithm:
    # Teams pick from lowest rank upwards.
    # For each team, check if they are #1 candidate in any unassigned sponsor.
    # If a team is #1 in multiple sponsors, pick according to sponsor priority list:
    # 1. prensa_amarilla, 2. rincon_tabernero, 3. carniceria_da_boyz, 4. sindicato_malhechores.
    # If not #1, they wait until sponsors trickle down.
    
    # We resolve iterative top-choice matching:
    all_sponsors = ["prensa_amarilla", "rincon_tabernero", "carniceria_da_boyz", "sindicato_malhechores"]
    
    # Loop until all 4 sponsors are assigned
    while len(assigned_sponsors) < len(all_sponsors):
        unassigned_sponsors = [s for s in all_sponsors if s not in assigned_sponsors]
        if not unassigned_sponsors:
            break
            
        # Determine who leads each unassigned sponsor (among unassigned teams)
        sponsor_leaders = {} # sponsor -> best unassigned team_id
        for s in unassigned_sponsors:
            for tid in category_candidates[s]:
                if tid not in assigned_teams:
                    sponsor_leaders[s] = tid
                    break
                    
        if not sponsor_leaders:
            break
            
        # Check collisions: does any team lead multiple sponsors?
        # Teams choose in order of lowest in table (highest rank number)
        chosen_in_round = False
        for t_info in teams_by_lowest_rank:
            tid = t_info["team_id"]
            if tid in assigned_teams:
                continue
                
            led_sponsors = [s for s, leader_tid in sponsor_leaders.items() if leader_tid == tid]
            if led_sponsors:
                # Team chooses the first sponsor in priority order
                # Priority: prensa_amarilla > rincon_tabernero > carniceria_da_boyz > sindicato_malhechores
                chosen_sponsor = next(s for s in all_sponsors if s in led_sponsors)
                assigned_sponsors[chosen_sponsor] = tid
                assigned_teams.add(tid)
                chosen_in_round = True
                break
                
        if not chosen_in_round:
            # Fallback if no leaders matched
            for s in unassigned_sponsors:
                if s in sponsor_leaders:
                    tid = sponsor_leaders[s]
                    assigned_sponsors[s] = tid
                    assigned_teams.add(tid)
                    break

    # Update database
    all_teams = session.exec(select(Team)).all()
    team_dict = {t.id: t for t in all_teams}
    
    # Clear previous sponsors
    for t in all_teams:
        t.current_sponsor_id = None
        
    for sponsor_id, team_id in assigned_sponsors.items():
        if team_id in team_dict:
            team_dict[team_id].current_sponsor_id = sponsor_id
            session.add(team_dict[team_id])
            
    session.commit()
    return assigned_sponsors
