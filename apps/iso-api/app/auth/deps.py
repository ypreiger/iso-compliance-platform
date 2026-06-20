"""Auth dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import decode_token
from app.db import get_conn

security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, id: str, email: str, roles: list[str]) -> None:
        self.id = id
        self.email = email
        self.roles = roles

    def require_role(self, *roles: str) -> None:
        if "admin" in self.roles:
            return
        if not any(r in self.roles for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> CurrentUser:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, roles, is_active FROM users WHERE id = %s",
            (payload["sub"],),
        ).fetchone()
    if not row or not row["is_active"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return CurrentUser(str(row["id"]), row["email"], list(row["roles"] or []))


def require_admin(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    user.require_role("admin")
    return user
