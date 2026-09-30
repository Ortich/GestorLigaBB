from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session

from app.auth import RuleError
from app.database import engine, init_db
from app.routers import admin, public
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if os.environ.get("BB_AUTO_SEED", "1") == "1":
        with Session(engine) as session:
            seed_if_empty(session)
    yield


app = FastAPI(title="Liga Blood Bowl", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RuleError)
async def rule_error_handler(_request, exc: RuleError):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})


app.include_router(public.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
