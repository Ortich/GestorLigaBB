"""Temporada completa de la liga de ejemplo, jugada contra la API real.

Recorre las 7 jornadas (28 partidos) por la maquina de estados: ready check,
Fondo Menor, clima, plegaria, patada inicial, eventos en vivo y cierre del acta.
La semilla del generador deja el resultado fijo, para poder repetir la prueba.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine
from app.models import Match
from seed import seed_bounties, seed_calendar, seed_league_state, seed_sponsors, seed_teams

SEMILLA = 2020

# Del mas caro al mas barato. El equipo con Fondo Menor gasta lo que le cabe.
INCENTIVOS = (
    ("CHEF", 300_000, 1),
    ("WIZARD", 150_000, 1),
    ("BRIBE", 100_000, 3),
    ("EXTRA_TRAINING", 100_000, 2),
    ("WANDERING_APOTH", 100_000, 1),
    ("BLOODWEISER_KEG", 50_000, 2),
    ("WEATHER_MAGE", 30_000, 1),
    ("TEMP_CHEERLEADER", 20_000, 4),
    ("PART_TIME_COACH", 20_000, 4),
)


@dataclass
class Caja:
    """Oro de un equipo en un partido, partido a partido."""

    team: str
    antes: int
    despues: int
    ganancias: int
    muerte: int = 0
    despido: int = 0
    fichaje: int = 0
    recompensa: int = 0
    taberna: int = 0

    @property
    def delta(self) -> int:
        return self.despues - self.antes

    @property
    def plantilla(self) -> int:
        """Lo que dejan muertes y despidos una vez pagados los fichajes."""
        return self.muerte + self.despido - self.fichaje

    @property
    def explicado(self) -> int:
        return self.ganancias + self.recompensa + self.plantilla - self.taberna


@dataclass
class Acta:
    round_number: int
    home: str
    away: str
    home_td: int
    away_td: int
    home_cas: int
    away_cas: int
    home_fouls: int
    away_fouls: int
    home_passes: int
    away_passes: int
    home_points: int
    away_points: int
    weather: str
    prayer: str
    kick_off: str
    petty_cash: int
    petty_cash_team: str
    inducements: list[str]
    injuries: list[str]
    home_winnings: int
    away_winnings: int
    mvp_home: str
    mvp_away: str
    bounty: str
    mercy: list[str]
    despidos: list[str]
    fichajes: list[str]
    tesoreria: list[str]
    economia: list[str]
    cajas: list[Caja]
    sponsors: list[str]


@dataclass
class Temporada:
    semilla: int
    actas: list[Acta] = field(default_factory=list)
    jornadas: list[list[dict[str, Any]]] = field(default_factory=list)
    clasificacion: list[dict[str, Any]] = field(default_factory=list)
    patrocinadores: list[str] = field(default_factory=list)
    muertos: list[str] = field(default_factory=list)
    lesiones: list[str] = field(default_factory=list)


def sembrar() -> dict[str, str]:
    """Crea la liga de ejemplo y devuelve el PIN de cada equipo."""
    from app import rules

    pins = {spec["name"]: spec["pin"] for spec in rules.load_rosters()["seed_teams"]}
    with Session(engine) as session:
        seed_sponsors(session)
        seed_bounties(session)
        seed_teams(session)
        seed_calendar(session)
        rounds = session.exec(select(Match.round_number).order_by(Match.round_number.desc())).first()
        seed_league_state(session, rounds or 1)
    return pins


def simular(client: TestClient, semilla: int = SEMILLA) -> Temporada:
    # La aficion se tira en el servidor con el modulo random. Sembrarla aqui
    # deja el acta repetible sin tocar el generador de los eventos del partido.
    random.seed(semilla)
    rng = random.Random(semilla)
    pins = sembrar()
    temporada = Temporada(semilla=semilla)
    tokens: dict[int, dict[str, str]] = {}

    partidos = client.get("/api/matches").json()
    por_jornada: dict[int, list[dict[str, Any]]] = {}
    for partido in partidos:
        por_jornada.setdefault(partido["round_number"], []).append(partido)

    for jornada in sorted(por_jornada):
        for partido in por_jornada[jornada]:
            temporada.actas.append(_jugar(client, rng, pins, partido, tokens))
        tabla = client.get("/api/league/standings").json()
        temporada.jornadas.append(tabla)
        if jornada >= 3:
            temporada.patrocinadores = [
                f"{fila['sponsor_name']} → {fila['team_name']}"
                for fila in tabla
                if fila.get("sponsor_name")
            ]

    temporada.clasificacion = temporada.jornadas[-1]
    for acta in temporada.actas:
        for lesion in acta.injuries:
            if lesion.endswith("Muerto"):
                temporada.muertos.append(lesion)
            elif "-1 " in lesion or "Lesion persistente" in lesion:
                temporada.lesiones.append(lesion)
    return temporada


def _jugar(
    client: TestClient,
    rng: random.Random,
    pins: dict[str, str],
    resumen: dict[str, Any],
    tokens: dict[int, dict[str, str]],
) -> Acta:
    match_id = resumen["id"]
    home_id = resumen["home_team_id"]
    away_id = resumen["away_team_id"]
    home_name = resumen["home_team_name"]
    away_name = resumen["away_team_name"]
    headers = _token(client, tokens, home_id, pins[home_name])
    _token(client, tokens, away_id, pins[away_name])
    _mejorar_si_puede(client, tokens[home_id], home_id)
    _mejorar_si_puede(client, tokens[away_id], away_id)
    tesoreria_antes = {
        home_id: _tesoreria(client, home_id),
        away_id: _tesoreria(client, away_id),
    }

    _ok(client.post(f"/api/matches/{match_id}/ready-check", headers=headers))
    _ok(
        client.post(
            f"/api/matches/{match_id}/confirm",
            headers=headers,
            json={"team_id": home_id, "pin": pins[home_name]},
        )
    )
    pre = _ok(
        client.post(
            f"/api/matches/{match_id}/confirm",
            headers=headers,
            json={"team_id": away_id, "pin": pins[away_name]},
        )
    )
    if pre["status"] != "PRE_MATCH":
        raise RuntimeError(f"{home_name} vs {away_name} no entro en prepartido: {pre['status']}")

    comprados = _gastar_fondo_menor(client, headers, match_id, pre)
    clima = _ok(
        client.post(
            f"/api/matches/{match_id}/rolls",
            headers=headers,
            json={"kind": "WEATHER", "value": rng.randint(2, 12)},
        )
    )
    plegaria = _ok(
        client.post(
            f"/api/matches/{match_id}/rolls",
            headers=headers,
            json={
                "kind": "PRAYER",
                "value": rng.randint(1, 16),
                "team_id": pre["petty_cash_team_id"] or home_id,
            },
        )
    )
    patada = _ok(
        client.post(
            f"/api/matches/{match_id}/rolls",
            headers=headers,
            json={"kind": "KICK_OFF", "value": rng.randint(2, 12)},
        )
    )
    vivo = _ok(client.post(f"/api/matches/{match_id}/start", headers=headers))

    locales = [p for p in vivo["home_players"] if p["status"] == "ACTIVE"]
    visitantes = [p for p in vivo["away_players"] if p["status"] == "ACTIVE"]
    td_local = _contar(rng, (0.12, 0.38, 0.32, 0.14, 0.04))
    td_visit = _contar(rng, (0.12, 0.38, 0.32, 0.14, 0.04))
    cas_local = _contar(rng, (0.45, 0.40, 0.15))
    cas_visit = _contar(rng, (0.45, 0.40, 0.15))
    faltas_local = _contar(rng, (0.55, 0.35, 0.10))
    faltas_visit = _contar(rng, (0.55, 0.35, 0.10))
    pases_local = _contar(rng, (0.25, 0.40, 0.25, 0.10))
    pases_visit = _contar(rng, (0.25, 0.40, 0.25, 0.10))

    marcas = {home_id: {"td": 0, "cas": 0, "fouls": 0, "passes": 0}, away_id: {"td": 0, "cas": 0, "fouls": 0, "passes": 0}}
    primera_sangre: Optional[int] = None
    victimas: set[int] = set()
    mejor_caza: tuple[int, int] = (0, 0)  # valor, equipo atacante

    def anotar(equipo_id: int, plantilla: list[dict[str, Any]], veces: int) -> None:
        for _ in range(veces):
            if not plantilla:
                return
            jugador = rng.choice(plantilla)
            _ok(
                client.post(
                    f"/api/matches/{match_id}/events",
                    headers=headers,
                    json={"team_id": equipo_id, "event_type": "TD", "player_id": jugador["id"], "turn": rng.randint(1, 8)},
                )
            )
            marcas[equipo_id]["td"] += 1

    def golpear(equipo_id: int, plantilla: list[dict[str, Any]], rival: list[dict[str, Any]], veces: int) -> None:
        nonlocal primera_sangre, mejor_caza
        for _ in range(veces):
            atacantes = plantilla
            objetivos = [p for p in rival if p["id"] not in victimas]
            if not atacantes or not objetivos:
                return
            jugador = rng.choice(atacantes)
            victima = rng.choice(objetivos)
            resultado = _herida(rng)
            _ok(
                client.post(
                    f"/api/matches/{match_id}/events",
                    headers=headers,
                    json={
                        "team_id": equipo_id,
                        "event_type": "CAS",
                        "is_block_casualty": True,
                        "player_id": jugador["id"],
                        "victim_player_id": victima["id"],
                        "casualty_result": resultado,
                        "turn": rng.randint(1, 8),
                    },
                )
            )
            victimas.add(victima["id"])
            marcas[equipo_id]["cas"] += 1
            if primera_sangre is None:
                primera_sangre = equipo_id
            if victima["current_value"] > mejor_caza[0]:
                mejor_caza = (victima["current_value"], equipo_id)

    def repetir(equipo_id: int, plantilla: list[dict[str, Any]], tipo: str, veces: int, clave: str) -> None:
        for _ in range(veces):
            if not plantilla:
                return
            jugador = rng.choice(plantilla)
            _ok(
                client.post(
                    f"/api/matches/{match_id}/events",
                    headers=headers,
                    json={"team_id": equipo_id, "event_type": tipo, "player_id": jugador["id"], "turn": rng.randint(1, 8)},
                )
            )
            marcas[equipo_id][clave] += 1

    anotar(home_id, locales, td_local)
    anotar(away_id, visitantes, td_visit)
    golpear(home_id, locales, visitantes, cas_local)
    golpear(away_id, visitantes, locales, cas_visit)
    repetir(home_id, locales, "FOUL", faltas_local, "fouls")
    repetir(away_id, visitantes, "FOUL", faltas_visit, "fouls")
    repetir(home_id, locales, "PASS", pases_local, "passes")
    repetir(away_id, visitantes, "PASS", pases_visit, "passes")
    if rng.random() < 0.3 and visitantes:
        _ok(
            client.post(
                f"/api/matches/{match_id}/events",
                headers=headers,
                json={
                    "team_id": away_id,
                    "event_type": "INT",
                    "player_id": rng.choice(visitantes)["id"],
                    "turn": rng.randint(1, 8),
                },
            )
        )

    recompensa = _ganador_recompensa(
        vivo.get("bounty") or {},
        home_id,
        away_id,
        marcas,
        primera_sangre,
        mejor_caza[1],
    )
    # MVP: el primero de los nominados (mas interaccion). Determinista para la simulacion.
    detalle_vivo = client.get(f"/api/matches/{match_id}").json()
    cierre_body: dict[str, Any] = {
        "home_winnings_roll": rng.randint(1, 6),
        "away_winnings_roll": rng.randint(1, 6),
        "home_mvp_mode": "pick",
        "away_mvp_mode": "pick",
    }
    home_cands = detalle_vivo.get("home_mvp_candidates") or detalle_vivo["home_players"]
    away_cands = detalle_vivo.get("away_mvp_candidates") or detalle_vivo["away_players"]
    if home_cands:
        cierre_body["home_mvp_player_id"] = home_cands[0]["id"]
    if away_cands:
        cierre_body["away_mvp_player_id"] = away_cands[0]["id"]
    if recompensa is not None:
        cierre_body["bounty_winner_team_id"] = recompensa

    informe = _ok(client.post(f"/api/matches/{match_id}/complete", headers=headers, json=cierre_body))
    detalle = client.get(f"/api/matches/{match_id}").json()
    nombres = {p["id"]: p["name"] for p in [*detalle["home_players"], *detalle["away_players"]]}

    puntos_local, puntos_visit = _puntos(detalle["home_td"], detalle["away_td"])
    fondo_nombre = ""
    if pre["petty_cash_team_id"] == home_id:
        fondo_nombre = home_name
    elif pre["petty_cash_team_id"] == away_id:
        fondo_nombre = away_name

    bounty = informe.get("bounty_payout") or {}
    bounty_txt = ""
    if bounty:
        bounty_txt = f"Recompensa: {bounty['bounty']} para {bounty['team_name']} ({_oro(bounty['gold'])})."

    despidos, fichajes, cifras = _renovar_plantillas(
        client, tokens, pins, informe["injuries"], home_id, away_id, home_name, away_name
    )
    muerte_por_equipo: dict[str, int] = {}
    for pago in informe.get("rookie_safety_payouts") or []:
        muerte_por_equipo[pago["team_name"]] = muerte_por_equipo.get(pago["team_name"], 0) + int(pago["gold"])
    recompensa_equipo = bounty.get("team_name") if bounty else None
    recompensa_oro = int(bounty["gold"]) if bounty else 0

    tesoreria = []
    cajas: list[Caja] = []
    economia = _lineas_economia(home_name, away_name, informe)
    descartes = {
        home_name: int(informe.get("home_discarded") or 0),
        away_name: int(informe.get("away_discarded") or 0),
    }
    for team_id, team_name, ganancias in (
        (home_id, home_name, informe["home_winnings"]),
        (away_id, away_name, informe["away_winnings"]),
    ):
        despues = _tesoreria(client, team_id)
        antes = tesoreria_antes[team_id]
        caja = Caja(
            team=team_name,
            antes=antes,
            despues=despues,
            ganancias=ganancias,
            muerte=muerte_por_equipo.get(team_name, 0),
            despido=cifras[team_name]["despido"],
            fichaje=cifras[team_name]["fichaje"],
            recompensa=recompensa_oro if team_name == recompensa_equipo else 0,
            taberna=descartes[team_name],
        )
        cajas.append(caja)
        signo = "+" if caja.delta >= 0 else ""
        tesoreria.append(
            f"Tesoreria de {team_name}: {_oro(antes)} → {_oro(despues)} ({signo}{_oro(caja.delta)})."
        )

    return Acta(
        round_number=resumen["round_number"],
        home=home_name,
        away=away_name,
        home_td=detalle["home_td"],
        away_td=detalle["away_td"],
        home_cas=marcas[home_id]["cas"],
        away_cas=marcas[away_id]["cas"],
        home_fouls=marcas[home_id]["fouls"],
        away_fouls=marcas[away_id]["fouls"],
        home_passes=marcas[home_id]["passes"],
        away_passes=marcas[away_id]["passes"],
        home_points=puntos_local,
        away_points=puntos_visit,
        weather=_nombre_tirada(clima.get("weather"), clima.get("weather_roll")),
        prayer=_nombre_tirada(plegaria.get("prayer"), plegaria.get("prayer_roll")),
        kick_off=_nombre_tirada(patada.get("kick_off"), patada.get("kick_off_roll")),
        petty_cash=pre["petty_cash_amount"],
        petty_cash_team=fondo_nombre,
        inducements=comprados,
        injuries=[
            f"{item['player_name']} ({_equipo(item['team_id'], home_id, home_name, away_name)}): {item['effect']}"
            for item in informe["injuries"]
        ],
        home_winnings=informe["home_winnings"],
        away_winnings=informe["away_winnings"],
        mvp_home=nombres.get(detalle.get("home_mvp_player_id"), "—"),
        mvp_away=nombres.get(detalle.get("away_mvp_player_id"), "—"),
        bounty=bounty_txt,
        mercy=[
            f"Muerte: {pago['team_name']} cobra {_oro(pago['gold'])} "
            f"({pago['percentage']} % del valor actual) por {pago['player_name']}."
            for pago in informe.get("rookie_safety_payouts") or []
        ],
        despidos=despidos,
        fichajes=fichajes,
        tesoreria=tesoreria,
        economia=economia,
        cajas=cajas,
        sponsors=[
            f"{item['sponsor_name']} → {item['team_name']}"
            for item in informe.get("sponsors") or []
            if item.get("team_name")
        ],
    )


def formatear(temporada: Temporada) -> str:
    lineas = [
        f"Temporada simulada (semilla {temporada.semilla})",
        f"{len(temporada.actas)} partidos en {max(a.round_number for a in temporada.actas)} jornadas.",
        "",
    ]
    jornada_actual = 0
    for indice, acta in enumerate(temporada.actas):
        if acta.round_number != jornada_actual:
            if jornada_actual:
                lineas.extend(_tabla(temporada.jornadas[jornada_actual - 1]))
                lineas.append("")
            jornada_actual = acta.round_number
            lineas.append(f"Jornada {jornada_actual}")
        lineas.append(
            f"  {acta.home} {acta.home_td}–{acta.away_td} {acta.away}"
            f"   ({acta.home_points}-{acta.away_points} pts)"
        )
        lineas.append(
            f"    Eventos: TD {acta.home_td}–{acta.away_td}, bajas {acta.home_cas}–{acta.away_cas}, "
            f"faltas {acta.home_fouls}–{acta.away_fouls}, pases {acta.home_passes}–{acta.away_passes}."
        )
        lineas.append(f"    Clima: {acta.weather}. Patada inicial: {acta.kick_off}. Plegaria: {acta.prayer}.")
        if acta.petty_cash and acta.petty_cash_team:
            gasto = ", ".join(acta.inducements) if acta.inducements else "no gasta nada"
            lineas.append(f"    Fondo Menor: {_oro(acta.petty_cash)} para {acta.petty_cash_team} → {gasto}.")
        if acta.injuries:
            lineas.append("    Heridos: " + "; ".join(acta.injuries) + ".")
        lineas.append(f"    MVP: {acta.mvp_home} y {acta.mvp_away}.")
        for extra in (
            *acta.economia,
            *acta.mercy,
            *([acta.bounty] if acta.bounty else []),
            *acta.despidos,
            *acta.fichajes,
            *acta.tesoreria,
        ):
            lineas.append(f"    {extra}")
        if indice == len(temporada.actas) - 1 or temporada.actas[indice + 1].round_number != jornada_actual:
            if jornada_actual == len(temporada.jornadas):
                lineas.extend(_tabla(temporada.jornadas[jornada_actual - 1]))

    lineas.extend(["", "Clasificacion final"])
    lineas.extend(_tabla(temporada.clasificacion))
    lineas.extend(["", "Balance de oro"])
    lineas.extend(_balance(temporada))
    if temporada.patrocinadores:
        lineas.extend(["", "Patrocinadores al cierre"])
        lineas.extend(f"  {item}" for item in temporada.patrocinadores)
    if temporada.muertos:
        lineas.extend(["", "Muertos"])
        lineas.extend(f"  {item}" for item in temporada.muertos)
    graves = [item for item in temporada.lesiones if "Muerto" not in item]
    if graves:
        lineas.extend(["", "Bajas con secuela"])
        lineas.extend(f"  {item}" for item in graves)
    return "\n".join(lineas)


def _balance(temporada: Temporada) -> list[str]:
    """Suma la temporada. La plantilla es muerte + despido - fichaje."""
    totales: dict[str, dict[str, int]] = {}
    for acta in temporada.actas:
        for caja in acta.cajas:
            fila = totales.setdefault(
                caja.team,
                {
                    "antes": caja.antes,
                    "despues": caja.despues,
                    "ganancias": 0,
                    "recompensa": 0,
                    "plantilla": 0,
                    "taberna": 0,
                },
            )
            fila["despues"] = caja.despues
            fila["ganancias"] += caja.ganancias
            fila["recompensa"] += caja.recompensa
            fila["plantilla"] += caja.plantilla
            fila["taberna"] += caja.taberna

    lineas = [
        "    Equipo                      Inicio     Final   Ganancias  Recompensa  Plantilla     Taberna",
    ]
    suma_ganancias = suma_recompensa = suma_plantilla = suma_taberna = 0
    for nombre in sorted(totales, key=lambda n: -totales[n]["despues"]):
        fila = totales[nombre]
        suma_ganancias += fila["ganancias"]
        suma_recompensa += fila["recompensa"]
        suma_plantilla += fila["plantilla"]
        suma_taberna += fila["taberna"]
        lineas.append(
            f"    {nombre:<26} {_oro(fila['antes']):>10} {_oro(fila['despues']):>10}"
            f" {_oro(fila['ganancias']):>11} {_oro(fila['recompensa']):>11}"
            f" {_oro(fila['plantilla']):>10} {_oro(fila['taberna']):>11}"
        )
    lineas.append(
        f"    {'Total':<26} {'':>10} {'':>10}"
        f" {_oro(suma_ganancias):>11} {_oro(suma_recompensa):>11}"
        f" {_oro(suma_plantilla):>10} {_oro(suma_taberna):>11}"
    )
    lineas.append(
        "    Plantilla = oro de muertes + oro de despidos - coste de los fichajes que los sustituyen."
    )
    lineas.append(
        "    Taberna = oro que se descarta cuando la tesoreria pasa de 150.000 al cobrar el partido."
    )
    return lineas


def _tabla(filas: list[dict[str, Any]]) -> list[str]:
    lineas = ["    Pos  Equipo                      Pts  PJ  G  E  P   TD   Bajas  Patrocinador"]
    for fila in filas:
        td = f"{fila['td_for'] - fila['td_against']:+d}"
        cas = f"{fila['cas_for'] - fila['cas_against']:+d}"
        sponsor = fila.get("sponsor_name") or "—"
        lineas.append(
            f"    {fila['position']:>2}   {fila['team_name']:<26} {fila['points']:>3}"
            f"  {fila['played']:>2}  {fila['wins']:>1}  {fila['draws']:>1}  {fila['losses']:>1}"
            f"  {td:>4}  {cas:>5}  {sponsor}"
        )
    return lineas


def _gastar_fondo_menor(
    client: TestClient, headers: dict[str, str], match_id: int, pre: dict[str, Any]
) -> list[str]:
    equipo = pre["petty_cash_team_id"]
    if not equipo or pre["petty_cash_amount"] <= 0:
        return []
    from app import rules

    comprados: list[str] = []
    cantidades: dict[str, int] = {}
    detalle = pre
    for code, coste, maximo in INCENTIVOS:
        while cantidades.get(code, 0) < maximo and detalle["petty_cash_remaining"] >= coste:
            detalle = _ok(
                client.post(
                    f"/api/matches/{match_id}/inducements",
                    headers=headers,
                    json={"team_id": equipo, "code": code, "quantity": 1},
                )
            )
            cantidades[code] = cantidades.get(code, 0) + 1
    for code, _coste, _maximo in INCENTIVOS:
        if cantidades.get(code):
            ficha = rules.inducement_by_code(code) or {}
            comprados.append(f"{cantidades[code]}× {ficha.get('name', code)}")
    return comprados


def _ganador_recompensa(
    bounty: dict[str, Any],
    home_id: int,
    away_id: int,
    marcas: dict[int, dict[str, int]],
    primera_sangre: Optional[int],
    cazarrecompensas: int,
) -> Optional[int]:
    code = bounty.get("code")
    if code == "PRIMERA_SANGRE":
        return primera_sangre
    if code == "SHOWTIME":
        candidatos = [tid for tid, m in marcas.items() if m["passes"] >= 3]
        if not candidatos:
            return None
        return max(candidatos, key=lambda tid: marcas[tid]["passes"])
    if code == "GOLEADA":
        candidatos = [tid for tid, m in marcas.items() if m["td"] >= 3]
        if not candidatos:
            return None
        return max(candidatos, key=lambda tid: marcas[tid]["td"])
    if code == "JUEGO_LIMPIO":
        if marcas[home_id]["td"] > marcas[away_id]["td"] and marcas[home_id]["fouls"] == 0:
            return home_id
        if marcas[away_id]["td"] > marcas[home_id]["td"] and marcas[away_id]["fouls"] == 0:
            return away_id
        return None
    if code == "CAZARRECOMPENSAS":
        return cazarrecompensas or None
    return None


def _herida(rng: random.Random) -> str:
    tirada = rng.randint(1, 16)
    if tirada <= 6:
        return "BADLY_HURT"
    if tirada <= 9:
        return "SERIOUSLY_HURT"
    if tirada <= 12:
        return "SERIOUS_INJURY"
    if tirada == 13:
        return rng.choice(("LASTING_INJURY_MA", "LASTING_INJURY_ST"))
    if tirada == 14:
        return "LASTING_INJURY_AG"
    if tirada == 15:
        return rng.choice(("LASTING_INJURY_PA", "LASTING_INJURY_AV"))
    return "DEAD"


def _contar(rng: random.Random, pesos: tuple[float, ...]) -> int:
    tiro = rng.random()
    acumulado = 0.0
    for cantidad, peso in enumerate(pesos):
        acumulado += peso
        if tiro <= acumulado:
            return cantidad
    return len(pesos) - 1


def _puntos(home_td: int, away_td: int) -> tuple[int, int]:
    if home_td > away_td:
        return 3, 1 if home_td - away_td == 1 else 0
    if away_td > home_td:
        return 1 if away_td - home_td == 1 else 0, 3
    return 1, 1


def _nombre_tirada(entrada: Optional[dict[str, Any]], valor: Optional[int]) -> str:
    nombre = (entrada or {}).get("name") or "sin resultado"
    if valor is None:
        return nombre
    return f"{nombre} ({valor})"


def _equipo(team_id: int, home_id: int, home_name: str, away_name: str) -> str:
    return home_name if team_id == home_id else away_name


def _lineas_economia(home_name: str, away_name: str, informe: dict[str, Any]) -> list[str]:
    """Como se ha calculado el oro y como se han movido los hinchas."""
    lineas = []
    lados = (
        (
            home_name,
            informe["home_winnings"],
            informe.get("home_winner_bonus") or 0,
            informe.get("home_fans_before"),
            informe.get("home_fans_after"),
            informe.get("home_fans_roll"),
            informe.get("home_discarded") or 0,
            informe.get("home_winnings_roll"),
        ),
        (
            away_name,
            informe["away_winnings"],
            informe.get("away_winner_bonus") or 0,
            informe.get("away_fans_before"),
            informe.get("away_fans_after"),
            informe.get("away_fans_roll"),
            informe.get("away_discarded") or 0,
            informe.get("away_winnings_roll"),
        ),
    )
    # El informe de cierre no repite la tirada de 1D6: esta en el acta del partido.
    for nombre, oro, bono, antes, despues, dado, taberna, tirada, *_resto in lados:
        extra = " +1 victoria" if bono else ""
        cara = f"={tirada}" if tirada is not None else ""
        hinchas = f"{antes} hinchas" if antes is not None else "hinchas"
        linea = f"Oro de {nombre}: (1D6{cara}{extra} + {hinchas}) × 10.000 = {_oro(oro)}."
        if taberna:
            linea += (
                f" La taberna se queda {_oro(taberna)}: "
                "tus jugadores se han gastado el exceso de oro en la taberna local."
            )
        lineas.append(linea)
        if antes is not None and despues is not None:
            tirada = f" (2D6 = {dado})" if dado is not None else ""
            lineas.append(f"Hinchas de {nombre}: {antes} → {despues}{tirada}.")
    return lineas


def _oro(cantidad: int) -> str:
    return f"{cantidad:,}".replace(",", ".") + " mo"


def _token(
    client: TestClient, tokens: dict[int, dict[str, str]], team_id: int, pin: str
) -> dict[str, str]:
    if team_id not in tokens:
        tokens[team_id] = _login(client, team_id, pin)
    return tokens[team_id]


def _tesoreria(client: TestClient, team_id: int) -> int:
    return client.get(f"/api/teams/{team_id}").json()["treasury"]


def _mejorar_si_puede(client: TestClient, headers: dict[str, str], team_id: int) -> None:
    """Gasta 6 SPP en una habilidad. Sube el valor actual y deja el coste base quieto."""
    plantilla = client.get(f"/api/teams/{team_id}", headers=headers).json()
    for jugador in plantilla["players"]:
        if jugador["status"] in ("DEAD", "RETIRED") or jugador["spp"] < 6:
            continue
        habilidad = f"Oficio {jugador['spp']}"
        response = client.post(
            f"/api/teams/{team_id}/players/{jugador['id']}/advance",
            headers=headers,
            json={"code": "CHOSEN_PRIMARY", "skill": habilidad},
        )
        if response.status_code < 400:
            return


def _renovar_plantillas(
    client: TestClient,
    tokens: dict[int, dict[str, str]],
    pins: dict[str, str],
    injuries: list[dict[str, Any]],
    home_id: int,
    away_id: int,
    home_name: str,
    away_name: str,
) -> tuple[list[str], list[str], dict[str, dict[str, int]]]:
    nombres = {home_id: home_name, away_id: away_name}
    despidos: list[str] = []
    fichajes: list[str] = []
    cifras = {
        home_name: {"despido": 0, "fichaje": 0},
        away_name: {"despido": 0, "fichaje": 0},
    }
    for item in injuries:
        team_id = item["team_id"]
        team_name = nombres[team_id]
        headers = _token(client, tokens, team_id, pins[team_name])
        if _de_por_vida(item["effect"]):
            plantilla = client.get(f"/api/teams/{team_id}", headers=headers).json()
            jugador = next(p for p in plantilla["players"] if p["id"] == item["player_id"])
            antes = plantilla["treasury"]
            despues = _ok(
                client.delete(f"/api/teams/{team_id}/players/{jugador['id']}", headers=headers)
            )
            devuelto = despues["treasury"] - antes
            if devuelto != jugador["cost"]:
                raise RuntimeError(
                    f"El despido de {jugador['name']} devolvio {devuelto}, no el coste base {jugador['cost']}."
                )
            cifras[team_name]["despido"] += devuelto
            despidos.append(
                f"Despido: {team_name} echa a {jugador['name']} y recupera {_oro(devuelto)} "
                f"de coste base (valor actual {_oro(jugador['current_value'])})."
            )
            alta, coste = _fichar(client, headers, team_id, team_name, jugador["position"])
        elif item["effect"] == "Muerto":
            plantilla = client.get(f"/api/teams/{team_id}", headers=headers).json()
            jugador = next(p for p in plantilla["players"] if p["id"] == item["player_id"])
            alta, coste = _fichar(client, headers, team_id, team_name, jugador["position"])
        else:
            continue
        cifras[team_name]["fichaje"] += coste
        if alta:
            fichajes.append(alta)
    return despidos, fichajes, cifras


def _fichar(
    client: TestClient,
    headers: dict[str, str],
    team_id: int,
    team_name: str,
    position_name: str,
) -> tuple[Optional[str], int]:
    opciones = client.get(f"/api/teams/{team_id}/roster-options", headers=headers).json()
    plantilla = client.get(f"/api/teams/{team_id}", headers=headers).json()
    tesoreria = plantilla["treasury"]
    misma = next(
        (
            p
            for p in opciones["positions"]
            if p["name"] == position_name and p["remaining"] > 0 and p["cost"] <= tesoreria
        ),
        None,
    )
    if misma is None:
        posibles = [p for p in opciones["positions"] if p["remaining"] > 0 and p["cost"] <= tesoreria]
        if not posibles:
            return f"Fichaje: {team_name} no llega a cubrir la baja de {position_name}.", 0
        misma = min(posibles, key=lambda p: p["cost"])
    usados = {p["name"] for p in plantilla["players"]}
    nombre = f"Recluta {misma['name']}"
    candidato = nombre
    serie = 2
    while candidato in usados:
        candidato = f"{nombre} {serie}"
        serie += 1
    antes = tesoreria
    despues = _ok(
        client.post(
            f"/api/teams/{team_id}/players",
            headers=headers,
            json={"position_code": misma["code"], "name": candidato},
        )
    )
    coste = antes - despues["treasury"]
    return (
        f"Fichaje: {team_name} contrata a {candidato} ({misma['name']}) por {_oro(coste)}.",
        coste,
    )


def _de_por_vida(effect: str) -> bool:
    return effect.startswith("-1") or effect == "Lesion persistente"


def _login(client: TestClient, team_id: int, pin: str) -> dict[str, str]:
    body = _ok(client.post("/api/auth/login", json={"team_id": team_id, "pin": pin}))
    return {"Authorization": f"Bearer {body['token']}"}


def _ok(response: Any) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    return response.json()
