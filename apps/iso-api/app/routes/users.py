"""Admin user management."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.auth.deps import CurrentUser, require_admin
from app.db import audit, get_conn, rows_to_list

router = APIRouter(prefix="/admin/users", tags=["users"])


class UserCreate(BaseModel):
    email: EmailStr
    name: str = ""
    roles: list[str] = Field(default_factory=lambda: ["consultant"])


class UserUpdate(BaseModel):
    name: str | None = None
    roles: list[str] | None = None
    is_active: bool | None = None


VALID_ROLES = {"admin", "consultant", "supervisor", "viewer"}


def serialize_row(row: dict) -> dict:
    """Convert database row to JSON-serializable dict."""
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
    return result


@router.get("")
def list_users(admin: Annotated[CurrentUser, Depends(require_admin)]):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, email, name, roles, is_active, created_at
            FROM users ORDER BY created_at DESC
            """
        ).fetchall()
    return {"users": rows_to_list(rows)}


@router.post("")
def create_user(body: UserCreate, admin: Annotated[CurrentUser, Depends(require_admin)]):
    invalid = set(body.roles) - VALID_ROLES
    if invalid:
        raise HTTPException(status_code=400, detail=f"Invalid roles: {invalid}")
    uid = str(uuid4())
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE lower(email) = lower(%s)", (body.email,)
        ).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="User already exists")
        conn.execute(
            """
            INSERT INTO users (id, email, name, roles, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (uid, body.email.lower(), body.name or body.email.split("@")[0], body.roles),
        )
        audit(conn, admin.id, "user.invited", "user", uid, after=body.model_dump())
        conn.commit()
        row = conn.execute(
            "SELECT id, email, name, roles, is_active, created_at FROM users WHERE id = %s",
            (uid,),
        ).fetchone()
    return dict(row)


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    admin: Annotated[CurrentUser, Depends(require_admin)],
):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        name = body.name if body.name is not None else row["name"]
        roles = body.roles if body.roles is not None else row["roles"]
        is_active = body.is_active if body.is_active is not None else row["is_active"]
        if body.roles is not None:
            invalid = set(body.roles) - VALID_ROLES
            if invalid:
                raise HTTPException(status_code=400, detail=f"Invalid roles: {invalid}")
        conn.execute(
            """
            UPDATE users SET name = %s, roles = %s, is_active = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (name, roles, is_active, user_id),
        )
        # Convert row to JSON-serializable dict (handles UUID and datetime)
        before_dict = serialize_row(row)
        audit(conn, admin.id, "user.updated", "user", user_id, before=before_dict, after=body.model_dump())
        conn.commit()
        updated = conn.execute(
            "SELECT id, email, name, roles, is_active FROM users WHERE id = %s", (user_id,)
        ).fetchone()
    return dict(updated)
