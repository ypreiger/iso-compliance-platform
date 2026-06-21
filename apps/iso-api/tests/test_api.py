"""API integration tests (dry-run / CI)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ["USE_SQLITE"] = "1"
os.environ["SQLITE_PATH"] = "/tmp/iso-platform-test.db"
os.environ["AUTH_DEV_MODE"] = "1"
os.environ["ADMIN_EMAILS"] = "yaakovpreiger@gmail.com,valeria.preiger@gmail.com"

from app.db import ensure_schema  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
ADMIN = "yaakovpreiger@gmail.com"
ADMIN2 = "valeria.preiger@gmail.com"


@pytest.fixture(scope="module", autouse=True)
def _schema():
    if os.path.exists(os.environ["SQLITE_PATH"]):
        os.remove(os.environ["SQLITE_PATH"])
    ensure_schema()


def _token(email: str = ADMIN) -> str:
    r = client.post("/auth/dev-login", json={"email": email, "name": "Admin"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_auth_config_dev_mode():
    cfg = client.get("/auth/config").json()
    assert cfg["dev_mode"] is True
    assert cfg["saml_enabled"] is False


def test_saml_metadata_unconfigured():
    assert client.get("/auth/saml/metadata").status_code == 503


def test_dev_login_admin():
    body = client.post("/auth/dev-login", json={"email": ADMIN}).json()
    assert "admin" in body["user"]["roles"]


def test_dev_login_second_admin():
    body = client.post("/auth/dev-login", json={"email": ADMIN2}).json()
    assert "admin" in body["user"]["roles"]


def test_dev_login_rejects_unknown():
    r = client.post("/auth/dev-login", json={"email": "stranger@example.com"})
    assert r.status_code == 403


def test_admin_list_users():
    h = {"Authorization": f"Bearer {_token()}"}
    r = client.get("/admin/users", headers=h)
    assert r.status_code == 200
    emails = [u["email"] for u in r.json()["users"]]
    assert ADMIN in emails
    assert ADMIN2 in emails


def test_admin_add_user():
    h = {"Authorization": f"Bearer {_token()}"}
    r = client.post(
        "/admin/users",
        headers=h,
        json={"email": "consultant@test.com", "roles": ["consultant"]},
    )
    assert r.status_code == 200
    r2 = client.post("/auth/dev-login", json={"email": "consultant@test.com"})
    assert r2.status_code == 200


def test_iso_bilingual_viewer():
    h = {"Authorization": f"Bearer {_token()}"}
    r = client.get("/v1/iso/clauses?standard=ISO9001&language=en", headers=h)
    assert r.status_code == 200
    clauses = r.json()["clauses"]
    assert len(clauses) >= 1
    assert "organization" in clauses[0]["text"].lower()
    assert "[binary:" not in clauses[0]["text"]
    r_he = client.get("/v1/iso/clauses?standard=ISO9001&language=he", headers=h)
    assert r_he.status_code == 200
    assert r_he.json()["clauses"][0]["direction"] == "rtl"
    r2 = client.get("/v1/iso/clauses/4.1/bilingual?standard=ISO9001", headers=h)
    assert "en" in r2.json()["locales"]
    assert "he" in r2.json()["locales"]


def test_viewer_cannot_access_projects():
    h_admin = {"Authorization": f"Bearer {_token()}"}
    client.post(
        "/admin/users",
        headers=h_admin,
        json={"email": "viewer@test.com", "roles": ["viewer"]},
    )
    viewer_token = client.post("/auth/dev-login", json={"email": "viewer@test.com"}).json()["access_token"]
    h_viewer = {"Authorization": f"Bearer {viewer_token}"}
    assert client.get("/v1/projects", headers=h_viewer).status_code == 403
    assert client.get("/v1/iso/clauses?standard=ISO9001&language=en", headers=h_viewer).status_code == 200
    me = client.get("/auth/me", headers=h_viewer).json()
    assert me["can_access_projects"] is False
    assert "viewer" in me["roles"]


def test_project_workflow():
    h = {"Authorization": f"Bearer {_token()}"}
    p = client.post(
        "/v1/projects",
        headers=h,
        json={"name": "Test Audit", "standards": ["ISO9001"]},
    ).json()
    pid = p["id"]
    client.put(
        f"/v1/projects/{pid}/context",
        headers=h,
        json={"context": {"industry": "medical", "sites": 1}},
    )
    client.post(
        f"/v1/projects/{pid}/findings",
        headers=h,
        json={"finding_text": "Document control gap observed"},
    )
    client.post(f"/v1/projects/{pid}/mapping/run-auto", headers=h)
    maps = client.get(f"/v1/projects/{pid}/mapping", headers=h).json()
    assert len(maps["items"]) >= 1
