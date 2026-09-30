# Liga de la Mesa

Asistente de mesa para una liga privada de Blood Bowl (BB2020), pensado para el móvil. No simula el partido: lleva plantillas, la clasificación, el prepartido y el acta en vivo.

## Arranque

En una terminal:

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

En otra:

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:3000` en el móvil (misma red) o en el ordenador. La interfaz habla con la API por el mismo origen.

La base es un solo fichero SQLite: `backend/data/league.db`. Se crea y se rellena sola la primera vez. Para volver a empezar, para el servidor, borra ese fichero y arranca de nuevo.

## Entrar

Ocho equipos, tesorería de 1.000.000 y un PIN de cuatro cifras:

| Equipo | Entrenador | PIN |
| --- | --- | --- |
| Leones de Altdorf | Marta Ruiz | 1111 |
| Colmillos de Hierro | Pedro Soler | 2222 |
| Hojas de Laurelorn | Elena Voss | 3333 |
| Yunque de Barak Varr | Thorin Koll | 4444 |
| Plaga de Crookback | Riki Skit | 5555 |
| Sombras de Naggaroth | Lilith Druch | 6666 |
| Tumba de Morr | Padre Anselmo | 7777 |
| Elegidos del Caos | Karl Zorn | 8888 |

El comisario entra en `/admin`. La llave por defecto es `nuffle`. Cámbiala con la variable `MASTER_KEY` antes de arrancar el backend.

## Qué calcula el servidor

- **VAE:** valor de los jugadores en juego, más segundas oportunidades, ayudantes, animadoras y apotecario. Fuera quedan tesorería, hinchas, MNG y muertos.
- **Fondo menor:** la diferencia exacta de VAE, solo para incentivos de ese partido. No se completa con tesorería y lo no gastado se pierde.
- **Puntos:** victoria 3, empate 1, derrota por un touchdown 1, derrota por más 0. Desempate por diferencia de touchdowns y luego por diferencia de bajas.
- **Red de novatos:** jornadas 1 y 2. Muerte o lesión permanente devuelve el 100%, el 50% y después el 25% del valor. Un MNG no cuenta.
- **Patrocinadores:** al cerrar la jornada 3, y cada jornada siguiente, se reparten Prensa Amarilla, Tabernero, Carnicería y Sindicato. Uno por equipo. Si alguien lidera dos métricas, elige el que está más abajo en la tabla; si no hay nadie delante del móvil, la prioridad automática es Sindicato, Tabernero, Carnicería y Prensa.
- **PEP:** touchdown 4, baja 2, intercepción 2, pase 1, MVP 4. Están en `backend/rules.json` por si la liga usa otra tabla.

Clima, patada, plegarias e incentivos también salen de `rules.json`. Los textos son recordatorios de mesa, no el reglamento oficial: el libro manda si hay duda.

## Tests

```bash
cd backend
python3 -m pytest
```
