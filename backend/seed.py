"""FASE 1 - Semilla de la liga.

Crea la base de datos SQLite con 8 equipos (11 jugadores cada uno, construidos
con un presupuesto de 1.000.000 de monedas de oro), los 4 patrocinadores
dinamicos, las recompensas semanales y el calendario round-robin de 7 jornadas.

Uso:
    python seed.py            # crea la liga si la base esta vacia
    python seed.py --reset    # borra la base y la vuelve a crear
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlmodel import Session, SQLModel, select  # noqa: E402

from app import rules, security  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from app.models import Bounty, LeagueState, Match, Player, Sponsor, Team  # noqa: E402

STARTING_BUDGET = 1_000_000


def round_robin(team_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Calendario de liga a una vuelta (metodo del circulo)."""
    ids = list(team_ids)
    if len(ids) % 2:
        ids.append(-1)  # descanso
    n = len(ids)
    rounds: list[list[tuple[int, int]]] = []
    for round_index in range(n - 1):
        pairs = []
        for i in range(n // 2):
            home, away = ids[i], ids[n - 1 - i]
            if -1 in (home, away):
                continue
            # Alterna local/visitante para repartir los partidos en casa.
            pairs.append((home, away) if round_index % 2 == 0 else (away, home))
        rounds.append(pairs)
        ids = [ids[0], ids[-1], *ids[1:-1]]
    return rounds


def seed_sponsors(session: Session) -> None:
    for definition in rules.sponsor_definitions():
        existing = session.exec(select(Sponsor).where(Sponsor.code == definition["code"])).first()
        if existing:
            continue
        session.add(
            Sponsor(
                code=definition["code"],
                name=definition["name"],
                metric=definition["metric"],
                description=definition.get("description", ""),
                benefit=definition.get("benefit", ""),
                priority=int(definition.get("priority", 0)),
            )
        )
    session.commit()


def seed_bounties(session: Session) -> None:
    for definition in rules.bounty_definitions():
        existing = session.exec(select(Bounty).where(Bounty.code == definition["code"])).first()
        if existing:
            continue
        session.add(
            Bounty(
                code=definition["code"],
                name=definition["name"],
                description=definition.get("description", ""),
                reward_gold=int(definition.get("reward_gold", 0)),
            )
        )
    session.commit()


def seed_teams(session: Session) -> list[Team]:
    rosters = rules.load_rosters()
    costs = rules.ctv_costs()
    created: list[Team] = []

    for spec in rosters["seed_teams"]:
        if session.exec(select(Team).where(Team.name == spec["name"])).first():
            continue

        race = rosters["races"][spec["race"]]
        positions = {p["code"]: p for p in race["positions"]}

        spent = spec["rerolls"] * race["reroll_cost"]
        spent += spec["assistant_coaches"] * costs["assistant_coach"]
        spent += spec["cheerleaders"] * costs["cheerleader"]
        spent += costs["apothecary"] if spec["apothecary"] else 0
        spent += sum(positions[line["code"]]["cost"] * line["count"] for line in spec["lineup"])

        if spent > STARTING_BUDGET:
            raise SystemExit(
                f"{spec['name']} se pasa del presupuesto: {spent:,} > {STARTING_BUDGET:,}"
            )

        team = Team(
            name=spec["name"],
            coach_name=spec["coach_name"],
            race=spec["race"],
            logo=spec.get("logo", "\U0001f6e1"),
            pin_hash=security.hash_pin(spec["pin"]),
            treasury=STARTING_BUDGET - spent,
            rerolls=spec["rerolls"],
            reroll_cost=race["reroll_cost"],
            assistant_coaches=spec["assistant_coaches"],
            cheerleaders=spec["cheerleaders"],
            apothecary=spec["apothecary"],
            fans=spec.get("fans", 1),
        )
        session.add(team)
        session.commit()
        session.refresh(team)

        names = list(race["names"])
        number = 1
        for line in spec["lineup"]:
            position = positions[line["code"]]
            for _ in range(line["count"]):
                player_name = names.pop(0) if names else f"Jugador {number}"
                session.add(
                    Player(
                        team_id=team.id,
                        number=number,
                        name=player_name,
                        position=position["name"],
                        ma=position["ma"],
                        st=position["st"],
                        ag=position["ag"],
                        pa=position.get("pa"),
                        av=position["av"],
                        skills=", ".join(position.get("skills", [])),
                        cost=position["cost"],
                        current_value=position["cost"],
                    )
                )
                number += 1
        session.commit()
        created.append(team)

    return created


def seed_calendar(session: Session) -> int:
    if session.exec(select(Match)).first():
        return 0
    teams = session.exec(select(Team).order_by(Team.id)).all()
    schedule = round_robin([t.id for t in teams])
    total = 0
    for round_index, pairs in enumerate(schedule, start=1):
        for home_id, away_id in pairs:
            session.add(Match(round_number=round_index, home_team_id=home_id, away_team_id=away_id))
            total += 1
    session.commit()
    return total


def seed_league_state(session: Session, total_rounds: int) -> None:
    state = session.get(LeagueState, 1)
    if state is None:
        state = LeagueState(id=1)
    state.total_rounds = max(total_rounds, 1)
    first_bounty = session.exec(select(Bounty).order_by(Bounty.id)).first()
    if state.active_bounty_id is None and first_bounty:
        state.active_bounty_id = first_bounty.id
    state.rookie_safety_last_round = int(rules.rookie_safety_config().get("last_round", 2))
    session.add(state)
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Semilla de la liga de Blood Bowl")
    parser.add_argument("--reset", action="store_true", help="Borra la base de datos existente")
    args = parser.parse_args()

    settings = get_settings()
    if args.reset:
        if settings.database_url.startswith("sqlite:///"):
            db_path = Path(settings.database_url.replace("sqlite:///", ""))
            if db_path.exists():
                db_path.unlink()
                print(f"Base de datos eliminada: {db_path}")
        else:
            SQLModel.metadata.drop_all(engine)

    init_db()

    with Session(engine) as session:
        seed_sponsors(session)
        seed_bounties(session)
        teams = seed_teams(session)
        created_matches = seed_calendar(session)
        rounds = session.exec(select(Match.round_number).order_by(Match.round_number.desc())).first()
        seed_league_state(session, rounds or 1)

        print(f"Equipos creados: {len(teams)}")
        for team in session.exec(select(Team).order_by(Team.name)).all():
            players = session.exec(select(Player).where(Player.team_id == team.id)).all()
            print(
                f"  {team.logo} {team.name:26} {team.race:16} "
                f"jugadores={len(players):2}  tesoreria={team.treasury:>8,} mo"
            )
        print(f"Partidos programados: {created_matches} en {rounds or 0} jornadas")
        print("\nPINs por defecto: 1111, 2222, ... 8888 (en el orden de rosters.json)")
        print(f"MASTER_KEY del panel de comisario: {settings.master_key}")


if __name__ == "__main__":
    main()
