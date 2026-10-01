"""Temporada completa: 8 equipos, 7 jornadas, 28 actas cerradas por la API."""

from __future__ import annotations

from simulacion import SEMILLA, simular


def _cifra(linea: str, marca: str) -> str:
    resto = linea.split(marca, 1)[1]
    return resto.split(" mo", 1)[0]


def test_temporada_completa_cuadra_la_clasificacion(client):
    temporada = simular(client, SEMILLA)

    assert len(temporada.actas) == 28
    assert {acta.round_number for acta in temporada.actas} == {1, 2, 3, 4, 5, 6, 7}
    assert all(acta.weather and acta.kick_off and acta.prayer for acta in temporada.actas)
    assert all(acta.home_winnings % 10_000 == 0 and acta.away_winnings % 10_000 == 0 for acta in temporada.actas)
    assert all(acta.tesoreria for acta in temporada.actas)
    assert sum(fila["fouls"] for fila in temporada.clasificacion) == sum(
        acta.home_fouls + acta.away_fouls for acta in temporada.actas
    )
    assert sum(fila["passes"] for fila in temporada.clasificacion) == sum(
        acta.home_passes + acta.away_passes for acta in temporada.actas
    )
    assert any(acta.despidos for acta in temporada.actas)
    assert any(acta.fichajes for acta in temporada.actas)
    assert any("coste base" in linea for acta in temporada.actas for linea in acta.despidos)
    assert any("valor actual" in linea for acta in temporada.actas for linea in acta.mercy)
    # Un lesionado mejorado, al despedirlo, devuelve el coste base y no el valor actual.
    assert any(
        "coste base" in linea and "valor actual" in linea and _cifra(linea, "recupera ") != _cifra(linea, "valor actual ")
        for acta in temporada.actas
        for linea in acta.despidos
    )

    puntos: dict[str, int] = {}
    for acta in temporada.actas:
        puntos[acta.home] = puntos.get(acta.home, 0) + acta.home_points
        puntos[acta.away] = puntos.get(acta.away, 0) + acta.away_points

    assert len(temporada.clasificacion) == 8
    for fila in temporada.clasificacion:
        assert fila["played"] == 7
        assert fila["wins"] + fila["draws"] + fila["losses"] == 7
        assert fila["points"] == puntos[fila["team_name"]]
        assert fila["td_diff"] == fila["td_for"] - fila["td_against"]
        assert fila["cas_diff"] == fila["cas_for"] - fila["cas_against"]

    # Derrota por un solo touchdown: 1 punto, no 0.
    estrechas = [
        acta
        for acta in temporada.actas
        if abs(acta.home_td - acta.away_td) == 1 and acta.home_td != acta.away_td
    ]
    assert estrechas
    for acta in estrechas:
        assert sorted((acta.home_points, acta.away_points)) == [1, 3]

    # Los patrocinadores no existen hasta cerrar la jornada 3, y nunca se repiten.
    for acta in temporada.actas:
        if acta.round_number < 3:
            assert acta.sponsors == []
    asignados = [acta.sponsors for acta in temporada.actas if acta.round_number >= 3 and acta.sponsors]
    assert asignados
    ultimo = asignados[-1]
    assert len(ultimo) == 4
    assert len({item.split(" → ")[1] for item in ultimo}) == 4

    # El marcador que deja el servidor es el de los touchdowns anotados.
    assert sum(fila["td_for"] for fila in temporada.clasificacion) == sum(
        acta.home_td + acta.away_td for acta in temporada.actas
    )

    # Resultado fijo de la semilla 2020, ya con despidos y fichajes.
    assert [fila["team_name"] for fila in temporada.clasificacion] == [
        "Reikland Reavers",
        "Athelorn Avengers",
        "Dwarf Giants",
        "Lustria Croakers",
        "Gouged Eye",
        "Chaos All-Stars",
        "Skavenblight Scramblers",
        "Naggaroth Nightmares",
    ]
    assert [fila["points"] for fila in temporada.clasificacion] == [15, 15, 13, 12, 12, 11, 7, 6]


def test_muertes_y_despidos_no_disparan_el_oro(client):
    """Despedir o reponer un muerto no deja oro de mas: el fichaje se come esa devolucion."""
    temporada = simular(client, SEMILLA)
    por_equipo: dict[str, dict[str, int]] = {}

    for acta in temporada.actas:
        for caja in acta.cajas:
            assert caja.delta == caja.explicado, (
                f"{caja.team} en la jornada {acta.round_number}: "
                f"la tesoreria cambia {caja.delta} y las partidas suman {caja.explicado}"
            )
            assert caja.taberna == max(0, caja.antes + caja.ganancias - 150_000), (caja.team, caja)
            fila = por_equipo.setdefault(
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

    for nombre, fila in por_equipo.items():
        assert fila["plantilla"] == 0, (nombre, fila)
        assert fila["despues"] - fila["antes"] == fila["ganancias"] + fila["recompensa"] - fila["taberna"], (
            nombre,
            fila,
        )
        assert fila["taberna"] > 0, (nombre, fila)
