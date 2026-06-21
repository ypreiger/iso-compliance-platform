"""Authentication routes — Google Workspace SAML + dev login."""
from __future__ import annotations

from typing import Annotated
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from fastapi.responses import RedirectResponse, Response
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from pydantic import BaseModel, EmailStr

from app.auth.deps import CurrentUser, get_current_user
from app.auth.jwt import create_token
from app.auth.saml_settings import build_saml_settings, request_dict_from_http, saml_settings_dict
from app.config import get_settings
from app.auth.roles import DEFAULT_NEW_USER_ROLES

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


from app.db import audit, get_conn


def _resolve_user(email: str, name: str, *, allow_self_register: bool = False) -> dict:
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
            if is_bootstrap_admin:
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
            if allow_self_register:
                uid = str(uuid4())
                roles = list(DEFAULT_NEW_USER_ROLES)
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
                return {"id": uid, "email": email_l, "name": name or email_l.split("@")[0], "roles": roles}
            raise HTTPException(
                status_code=403,
                detail="Not invited. Contact an administrator.",
            )
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


def _saml_display_name(auth: OneLogin_Saml2_Auth) -> str:
    attrs = auth.get_attributes()
    for key in ("displayName", "DisplayName", "name", "Name"):
        val = attrs.get(key)
        if val:
            return val[0] if isinstance(val, list) else str(val)
    first = attrs.get("firstName") or attrs.get("FirstName")
    last = attrs.get("lastName") or attrs.get("LastName")
    if first or last:
        parts = []
        if first:
            parts.append(first[0] if isinstance(first, list) else str(first))
        if last:
            parts.append(last[0] if isinstance(last, list) else str(last))
        return " ".join(parts)
    return ""


@router.get("/config")
def auth_config():
    settings = get_settings()
    return {
        "saml_enabled": settings.saml_configured,
        "google_enabled": settings.google_signin_enabled,
        "google_client_id": settings.google_client_id if settings.google_signin_enabled else "",
        "dev_mode": settings.auth_dev_mode,
        "admin_emails": list(settings.admin_emails),
    }


@router.get("/saml/metadata")
def saml_metadata():
    settings = get_settings()
    if not settings.saml_configured:
        raise HTTPException(status_code=503, detail="SAML not configured")
    meta = build_saml_settings(settings)
    return Response(content=meta.get_sp_metadata(), media_type="application/xml")


@router.get("/saml/login")
def saml_login(request: Request):
    settings = get_settings()
    if not settings.saml_configured:
        raise HTTPException(status_code=503, detail="SAML not configured")
    req = request_dict_from_http(request)
    auth = OneLogin_Saml2_Auth(req, saml_settings_dict(settings))
    return RedirectResponse(auth.login())


@router.post("/saml/acs")
async def saml_acs(request: Request):
    settings = get_settings()
    if not settings.saml_configured:
        raise HTTPException(status_code=503, detail="SAML not configured")
    form = await request.form()
    post_data = {key: form.get(key) for key in form.keys()}
    req = request_dict_from_http(request, post_data=post_data)
    auth = OneLogin_Saml2_Auth(req, saml_settings_dict(settings))
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        reason = auth.get_last_error_reason() or "; ".join(errors)
        raise HTTPException(status_code=400, detail=f"SAML authentication failed: {reason}")
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="SAML authentication failed")
    email = (auth.get_nameid() or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="SAML response missing email")
    name = _saml_display_name(auth) or email.split("@")[0]
    user = _resolve_user(email, name, allow_self_register=True)
    token = create_token(user["id"], user["email"], user["roles"])
    return RedirectResponse(f"{settings.iso_web_url}/auth/callback?access_token={token}")


class GoogleIdTokenRequest(BaseModel):
    credential: str


@router.post("/google/id-token", response_model=TokenResponse)
def google_id_token_login(body: GoogleIdTokenRequest):
    settings = get_settings()
    if not settings.google_signin_enabled:
        raise HTTPException(status_code=503, detail="Google sign-in not configured")
    try:
        info = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Google credential") from exc
    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise HTTPException(status_code=401, detail="Invalid token issuer")
    email = (info.get("email") or "").lower()
    if not email or not info.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google account email not verified")
    user = _resolve_user(email, info.get("name", ""), allow_self_register=True)
    return _token_response(user)


@router.get("/google/login")
def google_login():
    settings = get_settings()
    if not settings.google_oauth_redirect_enabled:
        raise HTTPException(status_code=503, detail="Google OAuth redirect not configured")
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
    if not settings.google_oauth_redirect_enabled:
        raise HTTPException(status_code=503, detail="Google OAuth redirect not configured")
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
    user = _resolve_user(info["email"], info.get("name", ""), allow_self_register=True)
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
    return {
        "id": user.id,
        "email": user.email,
        "roles": user.roles,
        "can_access_projects": user.can_access_projects,
    }
