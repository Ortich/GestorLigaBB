"""Temporada completa: 8 equipos, 7 jornadas, 28 actas cerradas por la API."""

from __future__ import annotations

from simulacion import SEMILLA, simular


def test_temporada_completa_cuadra_la_clasificacion(client):
    temporada = simular(client, SEMILLA)

    assert len(temporada.actas) == 28
    assert {acta.round_number for acta in temporada.actas} == {1, 2, 3, 4, 5, 6, 7}
    assert all(acta.weather and acta.kick_off and acta.prayer for acta in temporada.actas)

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

    # Resultado fijo de la semilla 2020. El triple empate a 15 lo rompe
    # la diferencia de touchdowns y, entre los dos primeros, la de bajas.
    assert [fila["team_name"] for fila in temporada.clasificacion] == [
        "Reikland Reavers",
        "Athelorn Avengers",
        "Chaos All-Stars",
        "Lustria Croakers",
        "Naggaroth Nightmares",
        "Dwarf Giants",
        "Skavenblight Scramblers",
        "Gouged Eye",
    ]
    assert [fila["points"] for fila in temporada.clasificacion] == [15, 15, 15, 13, 13, 11, 6, 6]
