from __future__ import annotations

from sqlmodel import Session, select

from app.league_engine import (
    bounty_profile,
    calculate_ctv,
    inducement_catalog,
    load_rules,
    lookup_prayer,
    lookup_roll,
    sponsor_profile,
)
from app.models import Match, MatchEvent, MatchInducement, Player, PlayerInjury, Team


def public_player(player: Player) -> dict:
    return {
        "id": player.id,
        "team_id": player.team_id,
        "name": player.name,
        "position": player.position,
        "number": player.number,
        "ma": player.ma,
        "st": player.st,
        "ag": player.ag,
        "pa": player.pa,
        "av": player.av,
        "skills": player.skills,
        "cost": player.cost,
        "current_value": player.current_value,
        "spp": player.spp,
        "status": player.status,
        "mng_until_round": player.mng_until_round,
        "injuries": player.injuries,
    }


def benefits_for(sponsor_id: str | None) -> dict:
    return {
        "chooses_kick": sponsor_id == "prensa",
        "fan_bonus": 1 if sponsor_id == "prensa" else 0,
        "free_reroll": sponsor_id == "tabernero",
        "ko_recovery": sponsor_id == "tabernero",
        "cas_bonus": sponsor_id == "carniceria",
        "free_bribe": sponsor_id == "sindicato",
    }


def public_team(team: Team, *, include_pin: bool = False) -> dict:
    data = {
        "id": team.id,
        "name": team.name,
        "coach_name": team.coach_name,
        "race": team.race,
        "race_key": team.race_key,
        "treasury": team.treasury,
        "rerolls": team.rerolls,
        "reroll_cost": team.reroll_cost,
        "assistant_coaches": team.assistant_coaches,
        "cheerleaders": team.cheerleaders,
        "apothecary": bool(team.apothecary),
        "fans": team.fans,
        "effective_fans": team.fans + (1 if team.current_sponsor_id == "prensa" else 0),
        "sponsor_id": team.current_sponsor_id,
        "sponsor": sponsor_profile(team.current_sponsor_id),
        "benefits": benefits_for(team.current_sponsor_id),
    }
    if include_pin:
        data["pin"] = team.pin
    return data


def _team_side(session: Session, team: Team, players: list[Player], snapshot_ctv: int | None) -> dict:
    breakdown = calculate_ctv(team, players)
    payload = public_team(team)
    payload["players"] = [public_player(player) for player in sorted(players, key=lambda item: item.number)]
    payload["ctv_live"] = breakdown["total"]
    payload["ctv_breakdown"] = breakdown
    payload["ctv"] = snapshot_ctv if snapshot_ctv is not None else breakdown["total"]
    return payload


def short_match(session: Session, match: Match) -> dict:
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    return {
        "id": match.id,
        "round_number": match.round_number,
        "status": match.status,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_name": home.name if home else "Equipo ausente",
        "away_name": away.name if away else "Equipo ausente",
        "home_coach": home.coach_name if home else "",
        "away_coach": away.coach_name if away else "",
        "home_race_key": home.race_key if home else "",
        "away_race_key": away.race_key if away else "",
        "home_td": match.home_td,
        "away_td": match.away_td,
        "home_ready": match.home_ready,
        "away_ready": match.away_ready,
    }


def build_match_state(session: Session, match: Match) -> dict:
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:
        from app.auth import RuleError

        raise RuleError("Falta un equipo de este partido.")
    home_players = list(session.exec(select(Player).where(Player.team_id == home.id)).all())
    away_players = list(session.exec(select(Player).where(Player.team_id == away.id)).all())
    events = list(session.exec(select(MatchEvent).where(MatchEvent.match_id == match.id)).all())
    inducements = list(
        session.exec(select(MatchInducement).where(MatchInducement.match_id == match.id)).all()
    )
    injuries = list(session.exec(select(PlayerInjury).where(PlayerInjury.match_id == match.id)).all())
    names = {player.id: player.name for player in home_players + away_players}
    rules = load_rules()
    spent = sum(item.quantity * item.unit_cost for item in inducements)
    cart = {item.inducement_id: item.quantity for item in inducements}
    catalog = []
    for item in inducement_catalog():
        catalog.append({**item, "qty": cart.get(item["id"], 0)})

    def tally(team_id: int) -> dict:
        counts = {kind: 0 for kind in ("TD", "CAS", "FOUL", "PASS", "INT", "MVP")}
        for event in events:
            if event.team_id == team_id and event.event_type in counts:
                counts[event.event_type] += 1
        return counts

    def rule_of(table: str, roll: int | None) -> dict | None:
        if roll is None:
            return None
        if table == "prayers":
            found = lookup_prayer(roll)
        else:
            found = lookup_roll(rules[table], roll)
        if not found:
            return {"roll": roll, "name": "Resultado sin ficha", "summary": "Anota el resultado y consulta el libro."}
        return {"roll": roll, "name": found["name"], "summary": found["summary"]}

    return {
        **short_match(session, match),
        "home": _team_side(session, home, home_players, match.home_ctv),
        "away": _team_side(session, away, away_players, match.away_ctv),
        "petty_cash_amount": match.petty_cash_amount,
        "petty_cash_team_id": match.petty_cash_team_id,
        "petty_cash_spent": spent,
        "petty_cash_remaining": max(match.petty_cash_amount - spent, 0),
        "inducements": catalog,
        "weather_roll": match.weather_roll,
        "weather": rule_of("weather", match.weather_roll),
        "prayer_roll": match.prayer_roll,
        "prayer": rule_of("prayers", match.prayer_roll),
        "kick_off_roll": match.kick_off_roll,
        "kick_off": rule_of("kickoff", match.kick_off_roll),
        "kicking_team_id": match.kicking_team_id,
        "bounty": bounty_profile(match.bounty_id),
        "current_turn": match.current_turn,
        "home_aggregates": tally(home.id),
        "away_aggregates": tally(away.id),
        "free_reroll_used": {"home": match.home_free_reroll_used, "away": match.away_free_reroll_used},
        "free_bribe_used": {"home": match.home_free_bribe_used, "away": match.away_free_bribe_used},
        "home_winnings": match.home_winnings,
        "away_winnings": match.away_winnings,
        "home_mvp_player_id": match.home_mvp_player_id,
        "away_mvp_player_id": match.away_mvp_player_id,
        "home_bounty_gold": match.home_bounty_gold,
        "away_bounty_gold": match.away_bounty_gold,
        "home_sponsor_gold": match.home_sponsor_gold,
        "away_sponsor_gold": match.away_sponsor_gold,
        "closure_applied": match.closure_applied,
        "events": [
            {
                "id": event.id,
                "team_id": event.team_id,
                "player_id": event.player_id,
                "player_name": names.get(event.player_id, "Jugador ausente"),
                "event_type": event.event_type,
                "turn": event.turn,
                "spp_awarded": event.spp_awarded,
            }
            for event in sorted(events, key=lambda item: item.id or 0)
        ],
        "injuries": [
            {
                "id": injury.id,
                "team_id": injury.team_id,
                "player_id": injury.player_id,
                "player_name": names.get(injury.player_id, "Jugador ausente"),
                "result": injury.result,
                "mercy_gold": injury.mercy_gold,
                "note": injury.note,
            }
            for injury in injuries
        ],
    }
