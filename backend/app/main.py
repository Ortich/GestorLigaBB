from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import rules
from app.config import get_settings
from app.db import init_db
from app.errors import LeagueError
from app.routers import admin, auth, league, matches, players, teams

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Asistente de gestion para una liga privada de Blood Bowl 2020.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LeagueError)
async def league_error_handler(_: Request, exc: LeagueError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(players.router)
app.include_router(league.router)
app.include_router(matches.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["meta"])
def health() -> dict[str, Any]:
    return {"status": "ok", "app": settings.app_name}


@app.get("/api/rules", tags=["meta"])
def get_rules() -> dict[str, Any]:
    """Textos oficiales (clima, patada inicial, plegarias, incentivos...)."""
    return rules.load_rules()


@app.get("/api/rosters", tags=["meta"])
def get_rosters() -> dict[str, Any]:
    return rules.load_rosters()


def _mount_frontend() -> None:
    dist = Path(settings.frontend_dist)
    if not dist.is_dir():
        return

    app.mount("/_next", StaticFiles(directory=dist / "_next"), name="next-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):  # pragma: no cover - servido en produccion
        relative = full_path.strip("/")
        # `trailingSlash: true` exporta cada ruta como <ruta>/index.html.
        for candidate in (
            dist / relative if relative else dist / "index.html",
            dist / relative / "index.html" if relative else dist / "index.html",
            dist / f"{relative}.html" if relative else dist / "index.html",
        ):
            if candidate.is_file():
                return FileResponse(candidate)
        fallback = dist / "404.html"
        if fallback.is_file():
            return FileResponse(fallback, status_code=404)
        return JSONResponse(status_code=404, content={"detail": "No encontrado"})


_mount_frontend()
