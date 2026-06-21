"""Role helpers for authorization."""
from __future__ import annotations

PROJECT_ROLES = frozenset({"consultant", "supervisor", "admin"})
DEFAULT_NEW_USER_ROLES = ("viewer",)


def has_project_access(roles: list[str]) -> bool:
    return bool(PROJECT_ROLES.intersection(roles))


def is_admin(roles: list[str]) -> bool:
    return "admin" in roles
