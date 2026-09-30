"""PIN hasheado + tokens de sesion firmados (HMAC), sin dependencias externas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any, Optional

from app.config import get_settings

_PIN_RE = re.compile(r"^\d{4}$")
_PBKDF2_ROUNDS = 120_000


class InvalidToken(Exception):
    pass


def validate_pin_format(pin: str) -> None:
    if not _PIN_RE.match(pin or ""):
        raise ValueError("El PIN debe tener exactamente 4 digitos.")


def hash_pin(pin: str) -> str:
    validate_pin_format(pin)
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, pin_hash: str) -> bool:
    if not pin_hash:
        return False
    try:
        algo, rounds, salt_hex, digest_hex = pin_hash.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", (pin or "").encode(), bytes.fromhex(salt_hex), int(rounds))
    return hmac.compare_digest(candidate.hex(), digest_hex)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload: bytes) -> bytes:
    key = get_settings().secret_key.encode()
    return hmac.new(key, payload, hashlib.sha256).digest()


def create_token(team_id: int, team_name: str, ttl: Optional[int] = None) -> str:
    settings = get_settings()
    body = {
        "team_id": team_id,
        "team_name": team_name,
        "exp": int(time.time()) + int(ttl if ttl is not None else settings.token_ttl_seconds),
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    return f"{_b64e(raw)}.{_b64e(_sign(raw))}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        body_b64, sig_b64 = token.split(".")
        raw = _b64d(body_b64)
        signature = _b64d(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise InvalidToken("Token malformado") from exc

    if not hmac.compare_digest(signature, _sign(raw)):
        raise InvalidToken("Firma invalida")

    payload = json.loads(raw)
    if payload.get("exp", 0) < time.time():
        raise InvalidToken("Token caducado")
    return payload


def check_master_key(candidate: Optional[str]) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, get_settings().master_key)
