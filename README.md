# Gestor de Liga Blood Bowl 2020

Asistente de gestion **mobile-first** para una liga privada de Blood Bowl (edicion 2020) de unos
8 entrenadores. No es un simulador: esta pensado para usarse con el movil a pie de mesa durante las
partidas fisicas.

Se encarga de las plantillas, la clasificacion con sus desempates, el prepartido completo (VAE,
Fondo Menor e incentivos), el registro de eventos en vivo y el cierre del acta.

## Que hace

| Area | Detalle |
| --- | --- |
| Login | Desplegable de equipos + PIN de 4 digitos. Sin correos ni contrasenas. |
| Plantilla | Roster con estado de salud, stats, habilidades, SPP y mejoras. |
| Clasificacion | Puntos y desempates automaticos. |
| Prepartido | Calculo de VAE, Fondo Menor y catalogo interactivo de incentivos. |
| Tiradas | Clima (2D6), Plegarias a Nuffle (1D16) y Patada Inicial (2D6) con la regla exacta en un popup. |
| En vivo | Vista a dos columnas con botones rapidos de TD, baja, pase, falta e intercepcion. Los SPP se suman solos. |
| Cierre | Ganancias (D6 x 10.000), MVP (+4 SPP), lesiones, Red de Seguridad de Novatos y reparto de patrocinadores. |
| Comisario | Panel oculto en `/admin` para forzar estados, corregir marcadores, mover oro, revivir jugadores y recalcular la liga. |

## Stack

* **Backend:** Python 3.12 + FastAPI + SQLModel (SQLAlchemy + Pydantic).
* **Base de datos:** SQLite en un unico fichero (`backend/liga.db`). Sin servidores externos.
* **Frontend:** Next.js 15 (App Router, export estatico) + React 19 + TailwindCSS.
* **Textos de reglas:** `backend/app/data/rules.json`, para no hardcodear textos largos en la UI.

El frontend es *stateless*: toda la logica de Blood Bowl vive en el backend y la UI solo pinta lo
que devuelve la API.

## Puesta en marcha

```bash
scripts/setup.sh     # instala dependencias y crea la liga con 8 equipos
scripts/build.sh     # compila el frontend y sirve todo desde http://localhost:8000
```

Para desarrollar con recarga en caliente (backend en el 8000 y frontend en el 3000):

```bash
scripts/dev.sh
```

### Manualmente

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python seed.py --reset          # crea equipos, calendario y patrocinadores
.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                                # http://localhost:3000
```

Documentacion interactiva de la API en <http://localhost:8000/docs>.

### La noche de liga

Lo mas comodo es levantar un solo proceso en el portatil del anfitrion y que todos los moviles
entren por la IP local:

```bash
scripts/build.sh
# los demas entran en http://<ip-del-portatil>:8000
```

## Datos de ejemplo

`seed.py` crea 8 equipos de razas distintas, cada uno con 11 jugadores construidos con un
presupuesto de 1.000.000 de monedas de oro (el sobrante queda en tesoreria), mas el calendario
round-robin de 7 jornadas, los 4 patrocinadores y las recompensas semanales.

| Equipo | Raza | Entrenador | PIN |
| --- | --- | --- | --- |
| Reikland Reavers | Humano | Marcos | 1111 |
| Gouged Eye | Orco | Javi | 2222 |
| Dwarf Giants | Enano | Raul | 3333 |
| Athelorn Avengers | Elfo Silvano | Nerea | 4444 |
| Skavenblight Scramblers | Skaven | Alba | 5555 |
| Naggaroth Nightmares | Elfo Oscuro | Diego | 6666 |
| Lustria Croakers | Hombre Lagarto | Sara | 7777 |
| Chaos All-Stars | Caos Elegido | Ivan | 8888 |

Clave del panel de comisario: `nuffle-2020`.

> Cambia los PIN y la `MASTER_KEY` antes de usarlo de verdad (ver Configuracion).

## Configuracion

Variables de entorno del backend (o un fichero `backend/.env`):

| Variable | Por defecto | Para que sirve |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///backend/liga.db` | Fichero SQLite de la liga. |
| `SECRET_KEY` | `cambia-esta-clave-en-produccion` | Firma de los tokens de sesion. |
| `MASTER_KEY` | `nuffle-2020` | Clave del panel `/admin`. |
| `FRONTEND_DIST` | `frontend/out` | Export estatico que sirve FastAPI. |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Origenes permitidos en modo desarrollo. |

En el frontend, `NEXT_PUBLIC_API_URL` permite apuntar a un backend en otro host.

## Reglas implementadas

### VAE (Valoracion Actual de Equipo)

Suma el valor de los jugadores **ACTIVOS** (excluye `MNG` y `DEAD`), las Segundas Oportunidades,
los Ayudantes de Entrenador, las Animadoras y el Apotecario. **La Tesoreria y los Hinchas Dedicados
no suman.**

### Fondo Menor (Petty Cash)

El equipo con menor VAE recibe exactamente `VAE_mayor - VAE_menor` en oro, gastable solo en
incentivos de ese partido. No puede anadir oro de su tesoreria y el credito sobrante se pierde. El
equipo de mayor VAE no puede comprar incentivos.

### Puntuacion y desempates

Victoria 3 puntos, empate 1, derrota por 1 TD de diferencia 1 y derrota por mas de 1 TD 0.
Desempates por este orden: diferencia de TD, diferencia de bajas causadas y TD a favor.

### Red de Seguridad de Novatos

Solo en las jornadas 1 y 2. Cuando un jugador muere o sufre una lesion permanente, su equipo
recibe en tesoreria el 100 % de su valor la primera vez, el 50 % la segunda y el 25 % a partir de
la tercera.

### Patrocinadores dinamicos

Se evaluan al final de cada jornada a partir de la Jornada 3 y cada uno se asigna a un unico equipo:

* **Prensa Amarilla** &rarr; ultimo clasificado.
* **El Rincon del Tabernero** &rarr; peor diferencia de TD.
* **Carniceria Da Boyz** &rarr; mas bajas causadas.
* **Sindicato de Malhechores** &rarr; mas faltas cometidas.

Si un equipo lidera dos metricas se queda solo con una y la otra pasa al siguiente del ranking. El
equipo peor clasificado elige primero; su eleccion sale de la preferencia que haya marcado en la
pestana *Patrocinadores*, y si no ha marcado ninguna se usa el orden por defecto de `rules.json`.

## Maquina de estados del partido

```
SCHEDULED -> READY_CHECK -> PRE_MATCH -> IN_PROGRESS -> COMPLETED
```

Cualquier transicion invalida devuelve un **HTTP 400** con un mensaje claro en castellano. El
comisario puede forzar cualquier estado (por ejemplo, reabrir un acta cerrada) desde `/admin`.

## Estructura del proyecto

```
backend/
  app/
    models.py          Modelos SQLModel (Team, Player, Match, MatchEvent, ...)
    db.py              Motor SQLite y sesiones
    league_engine.py   VAE, clasificacion, patrocinadores, mercy rule, recalculo
    match_service.py   Maquina de estados del partido y postpartido
    rules.py           Carga de rules.json / rosters.json
    security.py        Hash de PIN y tokens firmados
    serializers.py     Modelos de BD -> esquemas publicos
    routers/           auth, teams, league, matches, admin
    data/
      rules.json       Clima, patada inicial, plegarias, heridas, incentivos...
      rosters.json     Plantillas de las 8 razas y equipos de ejemplo
  seed.py              Semilla de la liga
  tests/               47 tests de motor y API
frontend/
  src/app/             /, /equipo, /partido, /liga, /reglas, /admin
  src/components/      AppShell, PinPad, hojas inferiores y pasos del partido
  src/lib/             Cliente de API, tipos y hooks
scripts/               setup.sh, dev.sh, build.sh
```

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

Cubren el calculo de VAE, el Fondo Menor, los desempates de la clasificacion, la asignacion de
patrocinadores con colisiones, la Red de Seguridad de Novatos, el flujo completo del partido y las
protecciones del panel de comisario.
