"""API tests for user registration and login flows (AC-29, AC-30, AC-01-03)."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session

from agrowave.modules.identity.infrastructure.row_models import (
    IdentityUserRow,
)


def test_ac29_duplicate_email_rejected(client: TestClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "name": "Original User",
        "password": "Password123!",
    }
    resp1 = client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 409
    data = resp2.json()
    assert data["code"] == "DuplicateEmail"


def test_ac30_unconfirmed_account_rejected(client: TestClient) -> None:
    register_payload = {
        "email": "unconfirmed@example.com",
        "name": "Unconfirmed User",
        "password": "Password123!",
    }
    reg_resp = client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201

    login_payload = {
        "email": "unconfirmed@example.com",
        "password": "Password123!",
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 403
    data = login_resp.json()
    assert data["code"] == "UnconfirmedAccount"


def test_ac01_03_login_returns_valid_jwt(client: TestClient, api_engine) -> None:
    # 1. Register
    register_payload = {
        "email": "valid_user@example.com",
        "name": "Valid User",
        "password": "Password123!",
    }
    reg_resp = client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201
    user_id = UUID(reg_resp.json()["id"])

    # 2. Mark user confirmed in DB directly to simulate confirmation
    with Session(api_engine) as session:
        user_row = session.get(IdentityUserRow, user_id)

        assert user_row is not None
        user_row.email_confirmed = True
        session.commit()

    # 3. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "valid_user@example.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "valid_user@example.com"
    assert body["user"]["role"] == "USER"
