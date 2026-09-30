"""Reglas de liga: valoración, puntos, red de novatos y patrocinadores.

Los textos largos viven en rules.json. Aquí solo está la aritmética.
"""

from __future__ import annotations

import json
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "rules.json"
VALID_STATUSES = ("SCHEDULED", "READY_CHECK", "PRE_MATCH", "IN_PROGRESS", "COMPLETED")
PLAYER_STATUSES = ("ACTIVE", "MNG", "DEAD")
EVENT_TYPES = ("TD", "CAS", "FOUL", "PASS", "INT", "MVP")
SPONSOR_IDS = ("prensa", "tabernero", "carniceria", "sindicato")


def load_rules() -> dict:
    with RULES_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def sideline_costs() -> dict:
    return load_rules()["sideline"]


def spp_for(event_type: str) -> int:
    return int(load_rules()["spp"].get(event_type, 0))


def calculate_ctv(team, players) -> dict:
    """VAE: jugadores ACTIVE + SO + ayudantes + animadoras + apotecario.

    Tesorería, hinchas, MNG y muertos quedan fuera.
    """
    costs = sideline_costs()
    active = []
    excluded = []
    for player in players:
        entry = {
            "id": player.id,
            "name": player.name,
            "status": player.status,
            "value": player.current_value,
        }
        if player.status == "ACTIVE":
            active.append(entry)
        else:
            excluded.append(entry)
    players_value = sum(item["value"] for item in active)
    rerolls_value = team.rerolls * team.reroll_cost
    assistants_value = team.assistant_coaches * costs["assistant_coach"]
    cheer_value = team.cheerleaders * costs["cheerleader"]
    apo_value = costs["apothecary"] if team.apothecary else 0
    total = players_value + rerolls_value + assistants_value + cheer_value + apo_value
    return {
        "players": players_value,
        "rerolls": rerolls_value,
        "reroll_count": team.rerolls,
        "reroll_cost": team.reroll_cost,
        "assistants": assistants_value,
        "assistant_count": team.assistant_coaches,
        "cheerleaders": cheer_value,
        "cheerleader_count": team.cheerleaders,
        "apothecary": apo_value,
        "total": total,
        "active_players": active,
        "excluded_players": excluded,
    }


def petty_cash(home_ctv: int, away_ctv: int) -> tuple[str | None, int]:
    """El equipo de menor VAE recibe la diferencia exacta. Si empatan, nadie."""
    if home_ctv == away_ctv:
        return None, 0
    if home_ctv < away_ctv:
        return "home", away_ctv - home_ctv
    return "away", home_ctv - away_ctv


def points_for_result(td_for: int, td_against: int) -> int:
    rules = load_rules()["scoring"]
    diff = td_for - td_against
    if diff > 0:
        return rules["win"]
    if diff == 0:
        return rules["draw"]
    if diff == -1:
        return rules["loss_by_one"]
    return rules["loss_by_more"]


def mercy_gold(value: int, already_suffered: int) -> int:
    """already_suffered es el número de bajas permanentes/muertes previas del equipo."""
    if already_suffered <= 0:
        return value
    if already_suffered == 1:
        return value // 2
    return value // 4


def mercy_applies(round_number: int) -> bool:
    return round_number in load_rules()["mercy"]["rounds"]


def build_standings(teams, matches, events) -> list[dict]:
    """Orden: puntos, diferencia de TD, diferencia de bajas."""
    index = {}
    for team in teams:
        index[team.id] = {
            "team_id": team.id,
            "name": team.name,
            "coach_name": team.coach_name,
            "race": team.race,
            "race_key": team.race_key,
            "sponsor_id": team.current_sponsor_id,
            "played": 0,
            "points": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "td_for": 0,
            "td_against": 0,
            "cas_for": 0,
            "cas_against": 0,
            "fouls": 0,
        }
    completed = [match for match in matches if match.status == "COMPLETED"]
    completed_ids = {match.id for match in completed}
    for match in completed:
        home = index.get(match.home_team_id)
        away = index.get(match.away_team_id)
        if not home or not away:
            continue
        home["played"] += 1
        away["played"] += 1
        home["td_for"] += match.home_td
        home["td_against"] += match.away_td
        away["td_for"] += match.away_td
        away["td_against"] += match.home_td
        home["points"] += points_for_result(match.home_td, match.away_td)
        away["points"] += points_for_result(match.away_td, match.home_td)
        for row, scored, conceded in (
            (home, match.home_td, match.away_td),
            (away, match.away_td, match.home_td),
        ):
            if scored > conceded:
                row["wins"] += 1
            elif scored == conceded:
                row["draws"] += 1
            else:
                row["losses"] += 1
    for event in events:
        if event.match_id not in completed_ids or event.team_id not in index:
            continue
        row = index[event.team_id]
        if event.event_type == "CAS":
            row["cas_for"] += 1
        elif event.event_type == "FOUL":
            row["fouls"] += 1
    cas_by_match_team: dict[tuple[int, int], int] = {}
    for event in events:
        if event.match_id not in completed_ids or event.event_type != "CAS":
            continue
        key = (event.match_id, event.team_id)
        cas_by_match_team[key] = cas_by_match_team.get(key, 0) + 1
    for match in completed:
        home_cas = cas_by_match_team.get((match.id, match.home_team_id), 0)
        away_cas = cas_by_match_team.get((match.id, match.away_team_id), 0)
        if match.home_team_id in index:
            index[match.home_team_id]["cas_against"] += away_cas
        if match.away_team_id in index:
            index[match.away_team_id]["cas_against"] += home_cas
    rows = list(index.values())
    for row in rows:
        row["td_diff"] = row["td_for"] - row["td_against"]
        row["cas_diff"] = row["cas_for"] - row["cas_against"]
    rows.sort(key=lambda row: (-row["points"], -row["td_diff"], -row["cas_diff"], row["name"]))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def _choose_sponsor(team_id: int, options: list[str], manual: dict | None) -> str:
    rules = load_rules()
    preference = list(rules.get("sponsor_auto_preference") or SPONSOR_IDS)
    picked = None
    if manual:
        raw = manual.get(team_id, manual.get(str(team_id)))
        if isinstance(raw, str):
            picked = raw
        elif isinstance(raw, list):
            for item in raw:
                if item in options:
                    picked = item
                    break
        if picked in options:
            return picked
    for sponsor in preference:
        if sponsor in options:
            return sponsor
    return options[0]


def assign_sponsors(rows: list[dict], manual: dict | None = None) -> tuple[dict[str, int], list[str]]:
    """Un patrocinador, un equipo. Si alguien lidera dos métricas, elige uno.

    Elige antes quien esté más abajo en la tabla. El patrocinio rechazado
    baja al siguiente de esa métrica que aún no tenga patrocinador.
    """
    if not rows:
        return {}, ["No hay equipos a los que asignar patrocinio."]
    rankings = {
        "prensa": [row["team_id"] for row in sorted(rows, key=lambda row: (-row["rank"], row["team_id"]))],
        "tabernero": [
            row["team_id"]
            for row in sorted(rows, key=lambda row: (row["td_diff"], -row["rank"], row["team_id"]))
        ],
        "carniceria": [
            row["team_id"]
            for row in sorted(rows, key=lambda row: (-row["cas_for"], -row["rank"], row["team_id"]))
        ],
        "sindicato": [
            row["team_id"]
            for row in sorted(rows, key=lambda row: (-row["fouls"], -row["rank"], row["team_id"]))
        ],
    }
    names = {row["team_id"]: row["name"] for row in rows}
    rank_of = {row["team_id"]: row["rank"] for row in rows}
    labels = {
        "prensa": "Prensa Amarilla",
        "tabernero": "El Rincón del Tabernero",
        "carniceria": "Carnicería Da Boyz",
        "sindicato": "Sindicato Malhechores",
    }
    assigned_team: dict[str, int] = {}
    team_has: set[int] = set()
    log: list[str] = []

    def candidate(sponsor: str) -> int | None:
        for team_id in rankings[sponsor]:
            if team_id not in team_has:
                return team_id
        return None

    guard = 0
    while len(assigned_team) < len(rankings) and guard < 24:
        guard += 1
        claims: dict[int, list[str]] = {}
        for sponsor in rankings:
            if sponsor in assigned_team:
                continue
            team_id = candidate(sponsor)
            if team_id is None:
                continue
            claims.setdefault(team_id, []).append(sponsor)
        if not claims:
            break
        collisions = [team_id for team_id, sponsors in claims.items() if len(sponsors) > 1]
        if collisions:
            chooser = max(collisions, key=lambda team_id: (rank_of[team_id], team_id))
            options = claims[chooser]
            pick = _choose_sponsor(chooser, options, manual)
            assigned_team[pick] = chooser
            team_has.add(chooser)
            rejected = [labels[item] for item in options if item != pick]
            extra = ""
            if rejected:
                extra = " Pasan al siguiente: " + ", ".join(rejected) + "."
            manual_note = ""
            if manual and (chooser in manual or str(chooser) in manual):
                manual_note = " Elección indicada por el equipo."
            else:
                manual_note = " Elección automática según prioridad de la liga."
            log.append(
                f"Colisión: {names[chooser]} (puesto {rank_of[chooser]}) lideraba "
                f"{', '.join(labels[item] for item in options)}. "
                f"Se queda con {labels[pick]}.{manual_note}{extra}"
            )
            continue
        parts = []
        for team_id, sponsors in claims.items():
            sponsor = sponsors[0]
            assigned_team[sponsor] = team_id
            team_has.add(team_id)
            parts.append(f"{labels[sponsor]} → {names[team_id]}")
        log.append("Sin colisión: " + "; ".join(parts) + ".")
    if len(assigned_team) < len(rankings):
        log.append("No se pudieron cubrir todos los patrocinios con los equipos disponibles.")
    return assigned_team, log


def round_robin(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Todos contra todos a una vuelta. Cada pareja se ve una vez."""
    ids: list[int] = list(team_ids)
    bye = -1
    if len(ids) % 2 == 1:
        ids.append(bye)
    count = len(ids)
    half = count // 2
    rotation = ids[:]
    rounds: list[list[tuple[int, int]]] = []
    for round_index in range(count - 1):
        pairs: list[tuple[int, int]] = []
        for slot in range(half):
            home = rotation[slot]
            away = rotation[-(slot + 1)]
            if home == bye or away == bye:
                continue
            if (round_index + slot) % 2 == 0:
                pairs.append((home, away))
            else:
                pairs.append((away, home))
        rounds.append(pairs)
        rotation = [rotation[0]] + [rotation[-1]] + rotation[1:-1]
    return rounds


def lookup_roll(table: list[dict], roll: int) -> dict | None:
    for entry in table:
        low = entry.get("min", entry.get("roll"))
        high = entry.get("max", entry.get("roll"))
        if low is not None and high is not None and low <= roll <= high:
            return entry
    return None


def lookup_prayer(roll: int) -> dict | None:
    for entry in load_rules()["prayers"]:
        if entry["roll"] == roll:
            return entry
    return None


def sponsor_profile(sponsor_id: str | None) -> dict | None:
    if not sponsor_id:
        return None
    for sponsor in load_rules()["sponsors"]:
        if sponsor["id"] == sponsor_id:
            return sponsor
    return None


def bounty_profile(bounty_id: str | None) -> dict | None:
    if not bounty_id:
        return None
    for bounty in load_rules()["bounties"]:
        if bounty["id"] == bounty_id:
            return bounty
    return None


def inducement_catalog() -> list[dict]:
    return load_rules()["inducements"]


def bounty_reward(bounty_id: str | None, *, td: int, cas: int, fouls: int, td_against: int) -> int:
    bounty = bounty_profile(bounty_id)
    if not bounty:
        return 0
    metric = bounty["metric"]
    minimum = bounty["min"]
    value = {
        "td": td,
        "cas": cas,
        "fouls": fouls,
        "clean_sheet": 1 if td_against == 0 else 0,
    }.get(metric, 0)
    if value >= minimum:
        return int(bounty["reward"])
    return 0
