"""Carga y consulta del fichero `rules.json` (textos oficiales BB2020).

Toda la UI se puebla desde aqui: no hay textos largos hardcodeados en las vistas.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional

from app.config import get_settings


@lru_cache
def load_rules() -> dict[str, Any]:
    path = get_settings().data_dir / "rules.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache
def load_rosters() -> dict[str, Any]:
    path = get_settings().data_dir / "rosters.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def reload_rules() -> None:
    load_rules.cache_clear()
    load_rosters.cache_clear()


def _lookup_table(table_key: str, roll: int) -> Optional[dict[str, Any]]:
    table = load_rules().get(table_key, {})
    for entry in table.get("entries", []):
        if entry.get("min") is not None and entry["min"] <= roll <= entry["max"]:
            return entry
    return None


def weather_entry(roll: int) -> Optional[dict[str, Any]]:
    return _lookup_table("weather", roll)


def kick_off_entry(roll: int) -> Optional[dict[str, Any]]:
    return _lookup_table("kick_off", roll)


def prayer_entry(roll: int) -> Optional[dict[str, Any]]:
    return _lookup_table("prayers_to_nuffle", roll)


def spp_for(event_type: str) -> int:
    return int(load_rules().get("spp", {}).get(event_type, 0))


def inducement_catalog() -> list[dict[str, Any]]:
    return load_rules().get("inducements", {}).get("catalog", [])


def inducement_by_code(code: str) -> Optional[dict[str, Any]]:
    for item in inducement_catalog():
        if item["code"] == code:
            return item
    return None


def advancement_by_code(code: str) -> Optional[dict[str, Any]]:
    for item in load_rules().get("advancements", []):
        if item["code"] == code:
            return item
    return None


def level_for_spp(spp: int) -> str:
    for level in load_rules().get("levels", []):
        if level["min"] <= spp <= level["max"]:
            return level["name"]
    return "Novato"


def ctv_costs() -> dict[str, int]:
    ctv = load_rules().get("ctv", {})
    return {
        "assistant_coach": int(ctv.get("assistant_coach_cost", 10_000)),
        "cheerleader": int(ctv.get("cheerleader_cost", 10_000)),
        "apothecary": int(ctv.get("apothecary_cost", 50_000)),
    }


def scoring_config() -> dict[str, Any]:
    return load_rules().get("scoring", {})


def rookie_safety_config() -> dict[str, Any]:
    return load_rules().get("rookie_safety", {})


def sponsor_definitions() -> list[dict[str, Any]]:
    return load_rules().get("sponsors", [])


def sponsor_rules() -> dict[str, Any]:
    return load_rules().get("sponsor_rules", {})


def bounty_definitions() -> list[dict[str, Any]]:
    return load_rules().get("bounties", [])


def post_match_config() -> dict[str, Any]:
    return load_rules().get("post_match", {})
