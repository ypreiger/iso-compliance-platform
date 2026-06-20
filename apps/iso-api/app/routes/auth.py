"""Authentication routes — Google OAuth + dev login."""
from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from app.auth.deps import CurrentUser, get_current_user
from app.auth.jwt import create_token
from app.config import get_settings
from app.db import audit, get_conn

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class DevLoginRequest(BaseModel):
    email: EmailStr
    name: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _resolve_user(email: str, name: str) -> dict:
    settings = get_settings()
    email_l = email.lower()
    is_bootstrap_admin = email_l in settings.admin_emails
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, name, roles, is_active FROM users WHERE lower(email) = %s",
            (email_l,),
        ).fetchone()
        if row and not row["is_active"]:
            raise HTTPException(status_code=403, detail="User deactivated")
        if not row:
            if not is_bootstrap_admin:
                raise HTTPException(
                    status_code=403,
                    detail="Not invited. Contact an administrator.",
                )
            uid = str(uuid4())
            roles = ["admin"]
            conn.execute(
                """
                INSERT INTO users (id, email, name, roles, is_active)
                VALUES (%s, %s, %s, %s, TRUE)
                """,
                (uid, email_l, name or email_l.split("@")[0], roles),
            )
            conn.commit()
            audit(conn, uid, "user.created", "user", uid, after={"email": email_l, "roles": roles})
            conn.commit()
            return {"id": uid, "email": email_l, "name": name, "roles": roles}
        if is_bootstrap_admin and "admin" not in (row["roles"] or []):
            roles = list(set(list(row["roles"] or []) + ["admin"]))
            conn.execute(
                "UPDATE users SET roles = %s, updated_at = NOW() WHERE id = %s",
                (roles, row["id"]),
            )
            conn.commit()
            row = {**row, "roles": roles}
        return {
            "id": str(row["id"]),
            "email": row["email"],
            "name": row["name"] or name,
            "roles": list(row["roles"] or []),
        }


def _token_response(user: dict) -> TokenResponse:
    token = create_token(user["id"], user["email"], user["roles"])
    return TokenResponse(access_token=token, user=user)


@router.get("/config")
def auth_config():
    settings = get_settings()
    return {
        "google_enabled": settings.google_configured,
        "dev_mode": settings.auth_dev_mode,
        "admin_emails": list(settings.admin_emails),
    }


@router.get("/google/login")
def google_login():
    settings = get_settings()
    if not settings.google_configured:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.iso_web_url}/auth/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.post("/google/callback")
async def google_callback(body: dict):
    settings = get_settings()
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    if not settings.google_configured:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.iso_web_url}/auth/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed")
        access = token_resp.json().get("access_token")
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Userinfo failed")
        info = user_resp.json()
    user = _resolve_user(info["email"], info.get("name", ""))
    return _token_response(user)


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(req: DevLoginRequest):
    settings = get_settings()
    if not settings.auth_dev_mode:
        raise HTTPException(status_code=404, detail="Dev login disabled")
    user = _resolve_user(req.email, req.name)
    return _token_response(user)


@router.get("/me")
def me(user: Annotated[CurrentUser, Depends(get_current_user)]):
    return {"id": user.id, "email": user.email, "roles": user.roles}
