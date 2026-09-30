"""Ocho equipos de salida, once jugadores cada uno y calendario a una vuelta."""

from __future__ import annotations

from sqlmodel import Session, select

from app.league_engine import round_robin
from app.models import LeagueState, Match, Player, Team


def _players(names, position, ma, st, ag, pa, av, skills, cost):
    return [
        {
            "name": name,
            "position": position,
            "ma": ma,
            "st": st,
            "ag": ag,
            "pa": pa,
            "av": av,
            "skills": skills,
            "cost": cost,
        }
        for name in names
    ]


TEAMS = [
    {
        "name": "Leones de Altdorf",
        "coach_name": "Marta Ruiz",
        "race": "Humanos",
        "race_key": "human",
        "pin": "1111",
        "rerolls": 3,
        "reroll_cost": 50_000,
        "assistant_coaches": 1,
        "cheerleaders": 2,
        "apothecary": 1,
        "fans": 3,
        "players": (
            _players(
                ["Otto Brandt", "Klaus Meier", "Pieter Hahn", "Franz Adler", "Uwe Stein", "Johan Kranz"],
                "Línea", 6, 3, 3, 4, 9, "", 50_000,
            )
            + _players(["Erich Vogel"], "Lanzador", 6, 3, 3, 2, 9, "Pase, Manos Firmes", 75_000)
            + _players(
                ["Lena Hof", "Sigi Roth"],
                "Receptor", 8, 2, 3, 4, 8, "Esquiva, Captura", 65_000,
            )
            + _players(["Karl Brom"], "Blitzer", 7, 3, 3, 4, 9, "Bloquear", 90_000)
            + _players(
                ["Gran Olaf"],
                "Ogro", 5, 5, 4, 5, 10,
                "Solitario, Poderoso, Hueso Duro, Lanzar Compañero, Siempre Hambriento",
                140_000,
            )
        ),
    },
    {
        "name": "Colmillos de Hierro",
        "coach_name": "Pedro Soler",
        "race": "Orcos",
        "race_key": "orc",
        "pin": "2222",
        "rerolls": 3,
        "reroll_cost": 60_000,
        "assistant_coaches": 2,
        "cheerleaders": 3,
        "apothecary": 1,
        "fans": 4,
        "players": (
            _players(
                ["Gruk", "Nazgob", "Uruk", "Bork"],
                "Línea orca", 5, 3, 3, 4, 9, "", 50_000,
            )
            + _players(
                ["Morg", "Thak", "Durg", "Skarn"],
                "Blitzer orco", 6, 3, 3, 4, 10, "Bloquear", 80_000,
            )
            + _players(
                ["Grom el Ancho", "Vaz"],
                "Big'Un", 5, 4, 4, 5, 10, "", 90_000,
            )
            + _players(
                ["Piedra"],
                "Troll", 4, 5, 5, 5, 11,
                "Solitario, Siempre Hambriento, Golpe Brutal, Lanzar Compañero, Regeneración",
                115_000,
            )
        ),
    },
    {
        "name": "Hojas de Laurelorn",
        "coach_name": "Elena Voss",
        "race": "Elfos silvanos",
        "race_key": "elf",
        "pin": "3333",
        "rerolls": 2,
        "reroll_cost": 50_000,
        "assistant_coaches": 0,
        "cheerleaders": 2,
        "apothecary": 1,
        "fans": 2,
        "players": (
            _players(
                ["Laurel", "Silen", "Elandil", "Miriel", "Thalion", "Aranel"],
                "Línea elfo", 6, 3, 2, 4, 8, "", 60_000,
            )
            + _players(["Aerendil"], "Lanzador", 6, 3, 2, 2, 8, "Pase", 75_000)
            + _players(
                ["Luthien", "Faelivrin"],
                "Receptor", 8, 3, 2, 3, 8, "Esquiva, Captura", 90_000,
            )
            + _players(
                ["Celeborn", "Galion"],
                "Bailarín", 8, 3, 2, 4, 8, "Bloquear, Esquiva, Salto", 100_000,
            )
        ),
    },
    {
        "name": "Yunque de Barak Varr",
        "coach_name": "Thorin Koll",
        "race": "Enanos",
        "race_key": "dwarf",
        "pin": "4444",
        "rerolls": 3,
        "reroll_cost": 50_000,
        "assistant_coaches": 3,
        "cheerleaders": 1,
        "apothecary": 1,
        "fans": 2,
        "players": (
            _players(
                ["Bardin", "Durgan", "Kragg", "Olaf", "Snorri"],
                "Bloqueador", 4, 3, 4, 5, 10, "Bloquear, Placaje, Cráneo Duro", 70_000,
            )
            + _players(
                ["Gottri", "Mordin"],
                "Corredor", 6, 3, 3, 4, 9, "Manos Firmes, Cráneo Duro", 85_000,
            )
            + _players(
                ["Hargin", "Durek"],
                "Blitzer enano", 5, 3, 3, 4, 10, "Bloquear, Cráneo Duro", 80_000,
            )
            + _players(
                ["Grim", "Thorek"],
                "Matatrolls", 5, 3, 4, None, 9, "Intrépido, Frenesí, Cráneo Duro", 95_000,
            )
        ),
    },
    {
        "name": "Plaga de Crookback",
        "coach_name": "Riki Skit",
        "race": "Skavens",
        "race_key": "skaven",
        "pin": "5555",
        "rerolls": 2,
        "reroll_cost": 50_000,
        "assistant_coaches": 0,
        "cheerleaders": 1,
        "apothecary": 0,
        "fans": 5,
        "players": (
            _players(
                ["Skritch", "Nit", "Pox", "Snik", "Queek", "Lurk"],
                "Línea skaven", 7, 3, 3, 4, 8, "", 50_000,
            )
            + _players(["Thanquol Jr."], "Lanzador", 7, 3, 3, 2, 8, "Pase, Manos Firmes", 65_000)
            + _players(
                ["Scurry", "Vetch"],
                "Corredor de alcantarilla", 9, 2, 2, 4, 8, "Esquiva, Paso Lateral", 85_000,
            )
            + _players(
                ["Kratch", "Splinter"],
                "Blitzer skaven", 7, 3, 3, 4, 9, "Bloquear", 90_000,
            )
        ),
    },
    {
        "name": "Sombras de Naggaroth",
        "coach_name": "Lilith Druch",
        "race": "Elfos oscuros",
        "race_key": "delf",
        "pin": "6666",
        "rerolls": 2,
        "reroll_cost": 50_000,
        "assistant_coaches": 1,
        "cheerleaders": 2,
        "apothecary": 1,
        "fans": 1,
        "players": (
            _players(
                ["Virex", "Nihila", "Drusa", "Khael"],
                "Línea oscura", 6, 3, 2, 4, 9, "", 70_000,
            )
            + _players(
                ["Sable", "Malix"],
                "Blitzer oscuro", 7, 3, 2, 3, 9, "Bloquear", 100_000,
            )
            + _players(
                ["Yrrith", "Lorcan"],
                "Corredor", 7, 3, 2, 3, 8, "Esquiva, Entrega", 90_000,
            )
            + _players(
                ["Crone", "Sorceress"],
                "Bruja", 7, 3, 2, 4, 8, "Frenesí, Esquiva", 110_000,
            )
            + _players(["Cold One"], "Lanzador", 6, 3, 2, 2, 9, "Pase, Nervios de Acero", 75_000)
        ),
    },
    {
        "name": "Tumba de Morr",
        "coach_name": "Padre Anselmo",
        "race": "No muertos",
        "race_key": "undead",
        "pin": "7777",
        "rerolls": 2,
        "reroll_cost": 70_000,
        "assistant_coaches": 1,
        "cheerleaders": 2,
        "apothecary": 0,
        "fans": 1,
        "players": (
            _players(
                ["Hueso", "Polvo", "Tumba"],
                "Zombi", 4, 3, 4, None, 9, "Regeneración", 40_000,
            )
            + _players(
                ["Clavo", "Costilla", "Fémur"],
                "Esqueleto", 5, 3, 4, None, 8, "Regeneración, Cráneo Duro", 40_000,
            )
            + _players(
                ["Ghoul I", "Ghoul II"],
                "Necrófago", 7, 3, 3, 4, 8, "Esquiva", 75_000,
            )
            + _players(
                ["Espectro", "Sudario"],
                "Espectro", 6, 3, 3, 4, 9, "Bloquear, Regeneración", 90_000,
            )
            + _players(
                ["Amón"],
                "Momia", 3, 5, 5, None, 10, "Poderoso, Regeneración", 125_000,
            )
        ),
    },
    {
        "name": "Elegidos del Caos",
        "coach_name": "Karl Zorn",
        "race": "Elegidos del Caos",
        "race_key": "chaos",
        "pin": "8888",
        "rerolls": 3,
        "reroll_cost": 60_000,
        "assistant_coaches": 1,
        "cheerleaders": 0,
        "apothecary": 1,
        "fans": 2,
        "players": (
            _players(
                ["Khorg", "Varn", "Slaath", "Nurg", "Tzeen", "Morkhai"],
                "Hombre bestia", 6, 3, 3, 4, 9, "Cuernos", 60_000,
            )
            +             _players(
                ["Brakka", "Vessa", "Hroth", "Skulda"],
                "Guerrero del Caos", 5, 4, 3, 5, 10, "", 100_000,
            )
            + _players(
                ["Minotauro"],
                "Minotauro", 5, 5, 4, None, 9,
                "Solitario, Frenesí, Cuernos, Golpe Brutal, Cráneo Duro",
                150_000,
            )
        ),
    },
]


def seed(session: Session) -> None:
    if session.exec(select(Team)).first():
        return
    teams: list[Team] = []
    for spec in TEAMS:
        team = Team(
            name=spec["name"],
            coach_name=spec["coach_name"],
            race=spec["race"],
            race_key=spec["race_key"],
            pin=spec["pin"],
            treasury=1_000_000,
            rerolls=spec["rerolls"],
            reroll_cost=spec["reroll_cost"],
            assistant_coaches=spec["assistant_coaches"],
            cheerleaders=spec["cheerleaders"],
            apothecary=spec["apothecary"],
            fans=spec["fans"],
        )
        session.add(team)
        session.flush()
        for number, player in enumerate(spec["players"], start=1):
            session.add(
                Player(
                    team_id=team.id,
                    number=number,
                    name=player["name"],
                    position=player["position"],
                    ma=player["ma"],
                    st=player["st"],
                    ag=player["ag"],
                    pa=player["pa"],
                    av=player["av"],
                    skills=player["skills"],
                    cost=player["cost"],
                    current_value=player["cost"],
                    spp=0,
                    status="ACTIVE",
                )
            )
        teams.append(team)
    fixtures = round_robin([team.id for team in teams])
    for round_number, pairs in enumerate(fixtures, start=1):
        for home_id, away_id in pairs:
            session.add(
                Match(
                    round_number=round_number,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    status="SCHEDULED",
                )
            )
    session.add(LeagueState(current_round=1, active_bounty_id="caza", sponsor_log=""))
    session.commit()


def seed_if_empty(session: Session) -> None:
    seed(session)
