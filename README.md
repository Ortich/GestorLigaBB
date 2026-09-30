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

La liga vive en un servidor de fuera. El PC de casa no tiene que estar encendido: cada entrenador
abre la misma direccion desde su movil, este donde este. Entrada, calculos y base de datos ocurren
en esa maquina.

No hace falta otro servidor de base de datos. Toda la liga es el fichero `backend/liga.db` dentro
de la maquina. Copiar ese fichero es la copia de seguridad.

### Servidor gratuito: Oracle Cloud Always Free

Es el sitio que encaja a coste cero. Da una maquina virtual pequena con disco propio, IP publica y
10 TB de salida al mes, dentro del plan Always Free. La app es un solo proceso de Python; con 1 GB
de RAM le sobra. El disco no se borra al reiniciar, que es lo que necesita SQLite.

Los planes gratuitos de Render, Railway o Fly no sirven: el disco es temporal o de pago, y al
reiniciar la liga desapareceria. Google Cloud regala una maquina `e2-micro`, pero la IP publica se
cobra (unos 3,60 USD al mes) y solo incluye 1 GB de trafico de salida. Supabase no aloja esta
aplicacion.

La cuenta de Oracle pide una tarjeta para comprobar la identidad. Mientras la maquina sea la forma
`VM.Standard.E2.1.Micro`, el disco el de serie (unos 50 GB) y no crees nada mas, el coste es 0.
La region de origen no se puede cambiar despues: elige la mas cercana a los entrenadores (en
Espana, Spain Central).

1. Crea la cuenta en <https://www.oracle.com/cloud/free/>.
2. Compute, Instances, Create instance.
   - Imagen: Ubuntu 24.04, marcada Always Free Eligible.
   - Shape: Change shape y elige `VM.Standard.E2.1.Micro` (AMD, 1 GB), tambien Always Free
     Eligible. Una forma mas grande si se cobra.
   - Red: la que propone el asistente, con *Assign a public IPv4 address*.
   - Claves SSH: *Generate a key pair* y descarga la clave privada.
   - Disco de arranque: dejalo en el tamano por defecto. No anadas discos.
3. Si aparece *Out of host capacity*, cambia el dominio de disponibilidad y reintenta. Sigue en la
   forma Micro. Si en la cuenta gratuita no hay sitio, pasar la cuenta a Pay As You Go no cobra
   los recursos Always Free; solo cobraria lo que se salga de ese limite.
4. Con la instancia en RUNNING, copia la IP publica.
5. Abre el puerto 80 en la red de Oracle, no solo dentro de la maquina. Entra en la subnet de la
   instancia, luego en su Security List, Add Ingress Rules: origen `0.0.0.0/0`, protocolo TCP,
   puerto 80.
6. Desde tu PC:

```bash
chmod 600 clave.key
ssh -i clave.key ubuntu@IP_PUBLICA
```

7. Dentro de la maquina:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/Ortich/GestorLigaBB.git
cd GestorLigaBB
sudo bash scripts/install-server.sh
```

El script instala dependencias, compila la interfaz, crea la liga, cambia los PIN de ejemplo por
otros aleatorios y deja un servicio que arranca solo. Al terminar imprime la direccion
(`http://IP_PUBLICA`), la clave del comisario y los PIN. Anotalos: no se vuelven a mostrar.
Tambien quedan en la maquina, solo para root:

```bash
sudo cat /etc/gestor-liga-pins.txt
sudo grep MASTER_KEY /etc/gestor-liga.env
```

### Un nombre fijo, en vez de la IP

El nombre se crea gratis en [DuckDNS](https://www.duckdns.org/): entras
con Google o GitHub, eliges algo como `miliga` y copias el token de la cuenta. En la maquina:

```bash
sudo bash scripts/update-dns.sh miliga TU_TOKEN
```

A partir de ahi cada entrenador abre `http://miliga.duckdns.org`, elige su equipo e introduce su
PIN. Cada cinco minutos la maquina comprueba su IP y, si ha cambiado, actualiza el nombre sola.

Parar la maquina y volver a encenderla no cambia la IP. La pierde si se borra la instancia. Para
que el numero tampoco se mueva en ese caso, en la consola de Oracle reserva una IP publica
(Networking, IP management, Reserved public IPs) y asignala a la instancia. Oracle no cobra esa
reserva.

Oracle puede parar una maquina Always Free si durante 7 dias casi no tiene uso. No borra el disco:
en la consola, Compute, Instances, Start. El nombre de DuckDNS sigue siendo el mismo. Cada
madrugada se guarda una copia en `backend/backups/`. De vez en cuando bajala tambien a tu PC:

```bash
scp -i clave.key ubuntu@IP_PUBLICA:~/GestorLigaBB/backend/liga.db ./liga-copia.db
```

### Probarla en tu PC

Sirve para ver la app antes de subirla. Solo existe mientras la terminal sigue abierta, y los
moviles de fuera de esa WiFi no llegan:

```bash
scripts/setup.sh     # una vez
scripts/start.sh     # Ctrl+C para pararla
```

`start.sh` abre <http://localhost:8000>. Los PIN de esa copia local son los de la tabla de mas
abajo. Para desarrollar la interfaz con recarga en caliente:

```bash
scripts/dev.sh
```

Documentacion interactiva de la API en <http://localhost:8000/docs>.

### Docker

En el PC no lo uses. En el servidor gratuito tampoco hace falta: `install-server.sh` levanta el
mismo proceso sin el demonio de Docker. La imagen queda por si ya administras otro VPS con
Docker. El fichero de la liga queda en `./data/liga.db`, fuera del contenedor.

```bash
docker compose up -d --build
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

Clave del panel de comisario en una copia local: `nuffle-2020`.

En el servidor, `install-server.sh` genera otra clave y otros PIN. Los de esta tabla solo valen
en la copia de tu PC.

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

Solo en las jornadas 1 y 2, y solo si el jugador muere. El equipo recibe el 100 % de su valor
actual (coste mas mejoras) la primera vez, el 50 % la segunda y el 25 % a partir de la tercera.
Una lesion de por vida no paga sola: el jugador sigue en la plantilla. Si se le despide, la
tesoreria recupera unicamente su coste base, sin las mejoras. Un zombi de 40.000 que vale 80.000
con habilidades devuelve 40.000 al despedirlo, y 80.000 si muere en esas dos primeras jornadas.

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
Dockerfile             Imagen unica, solo si el VPS ya usa Docker
docker-compose.yml     Arranque con el fichero de la liga en ./data
deploy/                Unidad systemd del servidor
scripts/               setup.sh, start.sh, install-server.sh, update-dns.sh, backup-liga.sh
```

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
python scripts/simular-liga.py
```

`simular-liga.py` juega las 7 jornadas de la liga de ejemplo (28 partidos) por la API y escribe
el acta. Usa una base temporal, asi que no toca `backend/liga.db`. La semilla es fija: el mismo
campeon sale cada vez.

Los tests cubren el calculo de VAE, el Fondo Menor, los desempates de la clasificacion, la
asignacion de patrocinadores con colisiones, la Red de Seguridad de Novatos, el flujo completo del
partido, una temporada entera y las protecciones del panel de comisario.
