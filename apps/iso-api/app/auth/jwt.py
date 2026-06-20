"""JWT session tokens."""
from __future__ import annotations

import time
from typing import Any

import jwt

from app.config import get_settings


def create_token(user_id: str, email: str, roles: list[str]) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
