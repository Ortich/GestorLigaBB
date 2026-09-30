from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Gestor Liga Blood Bowl"

    database_url: str = f"sqlite:///{BACKEND_DIR / 'liga.db'}"

    # Firma de los tokens de sesion emitidos tras el login con PIN.
    secret_key: str = "cambia-esta-clave-en-produccion"
    token_ttl_seconds: int = 60 * 60 * 24 * 30

    # Llave del panel de comisario (/admin).
    master_key: str = "nuffle-2020"

    # Directorio con el build estatico del frontend (opcional).
    frontend_dist: str = str(PROJECT_DIR / "frontend" / "out")

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Util para los tests, que sobreescriben variables de entorno."""
    get_settings.cache_clear()
    os.environ.pop("_SETTINGS_CACHED", None)
