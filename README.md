# GestorLigaBB — Asistente de Gestión de Liga Blood Bowl (Edición BB2020)

Aplicación web **Mobile-First** diseñada para gestionar una liga privada de Blood Bowl (Edición BB2020) para 8 entrenadores. Funciona como **asistente de gestión a pie de mesa** en el móvil durante las partidas físicas, gestionando plantillas (rosters), cálculo de tabla de clasificación y desempates, automatización del prepartido (cálculo de VAE e incentivos/Petty Cash), registro de eventos en vivo y panel de comisionado.

---

## 🏈 Características Principales

### 1. Valoración Actual de Equipo (VAE / CTV) y Petty Cash
* **Cálculo de VAE:** Suma del valor de todos los jugadores `ACTIVE` (excluye `MNG` y `DEAD`), más Segundas Oportunidades (Rerolls), Ayudantes de entrenador, Animadoras y Apotecario. La Tesorería y los Hinchas (Dedicated Fans) **no** suman a la VAE.
* **Petty Cash (Fondo Menor):** En el prepartido, el equipo con menor VAE recibe exactamente la diferencia en monedas de oro (`VAE_mayor - VAE_menor`) como crédito para gastar en el catálogo interactivo de incentivos (Sobornos, Barriles de Bloodweiser, Apotecarios ambulantes, Hechicero, Mercenarios, etc.). El crédito no gastado se pierde al finalizar el prepartido.

### 2. Red de Seguridad de Novatos (Mercy Rule)
* Activa exclusivamente durante la **Jornada 1 y 2**.
* Si un jugador sufre una baja permanente o muere:
  * **1ª baja:** El equipo recibe el **100%** de su valor en la tesorería.
  * **2ª baja:** Recibe el **50%**.
  * **3ª baja en adelante:** Recibe el **25%**.

### 3. Puntuación y Desempates Oficiales
* **Victoria:** 3 puntos.
* **Empate:** 1 punto.
* **Derrota por 1 TD de diferencia:** 1 punto de consolación.
* **Derrota por >1 TD:** 0 puntos.
* **Criterios de Desempate:**
  1. Diferencia de Touchdowns (`TD favor - TD contra`).
  2. Diferencia de Bajas causadas (`CAS favor - CAS contra`).
  3. Total de Touchdowns anotados a favor.

### 4. Sponsors Dinámicos (Catch-up Mechanic)
Se evalúan al final de cada jornada a partir de la **Jornada 3**:
* **Prensa Amarilla:** Asignado al último clasificado (+1 Fan Factor permanente y elige patada inicial).
* **El Rincón del Tabernero:** Peor diferencial de TD (+1 a recuperar KO y 1 Reroll gratis por partido).
* **Carnicería Da Boyz:** Más bajas causadas (+20.000 mo si causa $\ge 2$ bajas en el partido).
* **Sindicato Malhechores:** Más faltas cometidas (1 Soborno gratis en cada partido).
* *Resolución de colisiones:* Si un equipo lidera varias categorías, el equipo peor clasificado en la tabla elige primero y el sponsor sobrante pasa al siguiente clasificado en esa métrica.

### 5. Flujo del Asistente de Partido (Máquina de Estados)
1. **READY_CHECK:** Ambos entrenadores confirman asistencia física introduciendo su PIN en el mismo dispositivo móvil.
2. **PRE_MATCH:** Comparación automática de VAE, concesión de Petty Cash con carrito de compra de incentivos, y tiradas con popup explicativo de reglas oficiales para:
   * Clima (2D6)
   * Plegarias a Nuffle (1D16)
   * Patada Inicial (2D6)
3. **IN_PROGRESS:** Marcador en vivo, control de turnos (1-8) y partes (1ª/2ª), lista táctil de jugadores a pie de campo con botones rápidos (`+TD`, `+Baja`, `+Pase`, `+Intercepción`, `+Falta`), asignación automática de SPP (Star Player Points) y registro de eventos con botón de deshacer/revertir.
4. **COMPLETED:** Tiradas de ganancias de oro (1D6 x 10.000 mo + bonus de sponsors), elección de MVP (+4 SPP) y registro de lesiones graves con cálculo automático de indemnizaciones de la Mercy Rule.

### 6. Modo Administrador (Panel del Comisionado)
* Acceso protegido por `MASTER_KEY` (`bbmaster2026`).
* **Gestor de Actas:** Permite forzar el estado de cualquier partido (reabrir partidos completados a en vivo), modificar marcadores y borrar eventos.
* **Gestor de Tesorería y Hospital:** Ajustar oro de cualquier equipo y revivir jugadores (`DEAD` $\to$ `ACTIVE`), limpiar `MNG` o modificar SPP.
* **Trigger de Recálculo:** Botón para recalcular standings y reasignar sponsors dinámicos desde cero.

---

## 🛠️ Stack Tecnológico

* **Backend:** Python 3.12 con **FastAPI**.
* **Base de Datos:** SQLite con **SQLModel** (Pydantic + SQLAlchemy) en un único archivo (`bloodbowl.db`).
* **Frontend:** **React** (Vite) + **TailwindCSS** + **Lucide Icons**, optimizado para móvil (*Mobile-First*).
* **Reglas:** `rules.json` con catálogo oficial de clima, patada inicial, plegarias a Nuffle e incentivos.

---

## 👥 Equipos Iniciales y PINs por Defecto

La base de datos viene sembrada con 8 equipos y 11 jugadores por plantilla:

| # | Equipo | Raza | Entrenador | PIN por defecto |
|---|--------|------|------------|-----------------|
| 1 | **Reikland Reavers** | Humanos | Coach Miller | `1111` |
| 2 | **Gouged Eye** | Orcos | Coach Varag | `2222` |
| 3 | **Athel Loren Foresters** | Elfos Silvanos | Coach Jordell | `3333` |
| 4 | **Dwarf Giants** | Enanos | Coach Grim | `4444` |
| 5 | **Champions of Death** | No-Muertos | Coach Tom | `5555` |
| 6 | **Skavenblight Scramblers** | Skaven | Coach Queek | `6666` |
| 7 | **Doom Diver Renegades** | Elegidos del Caos | Coach Malakor | `7777` |
| 8 | **Lustria Croakers** | Hombres Lagarto | Coach Tehenhauin | `8888` |

**Clave de Comisionado (Master Key):** `bbmaster2026`

---

## 🚀 Puesta en Marcha Rápida

### Opción 1: Script Automático Todo-en-Uno
```bash
./start.sh
```
El script instala dependencias si es necesario, compila el frontend, siembra la base de datos e inicia el servidor en `http://localhost:8000`.

### Opción 2: Manual paso a paso

1. **Instalar dependencias de Python:**
```bash
pip install -r requirements.txt
```

2. **Compilar el frontend:**
```bash
cd frontend
npm install
npm run build
cd ..
```

3. **Sembrar base de datos inicial:**
```bash
python3 seed.py
```

4. **Iniciar el servidor:**
```bash
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```
Abre en tu navegador móvil u ordenador: `http://localhost:8000`.

---

## 🧪 Ejecutar Tests

La suite incluye pruebas unitarias del motor de reglas (`test_league_engine.py`) y pruebas de integración de la API REST (`test_api.py`):

```bash
python3 -m pytest test_league_engine.py test_api.py -v
```
