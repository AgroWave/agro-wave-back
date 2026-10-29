"""API tests for auth guard and protected endpoints (AC-01-04)."""

import time

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow


def test_ac01_04_revoked_token_is_unauthorized(client: TestClient, api_engine) -> None:
    # 1. Register & activate user
    client.post(
        "/api/v1/auth/register",
        json={"email": "guard@example.com", "name": "Guard User", "password": "Password123!"},
    )
    with Session(api_engine) as session:
        statement = select(IdentityUserRow).where(IdentityUserRow.email == "guard@example.com")
        user_row = session.exec(statement).first()
        assert user_row is not None
        user_row.email_confirmed = True
        session.commit()

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "guard@example.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Access /auth/me - succeeds
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "guard@example.com"

    # 4. Logout (revoking token)
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # 5. Access /auth/me again with the revoked token - fails 401
    me_after_logout = client.get("/api/v1/auth/me", headers=headers)
    assert me_after_logout.status_code == 401


def test_ac01_04_token_invalid_after_password_change(client: TestClient, api_engine) -> None:
    # 1. Register & activate user
    client.post(
        "/api/v1/auth/register",
        json={"email": "pwdchange@example.com", "name": "Pwd User", "password": "OldPassword123!"},
    )
    with Session(api_engine) as session:
        statement = select(IdentityUserRow).where(IdentityUserRow.email == "pwdchange@example.com")
        user_row = session.exec(statement).first()
        assert user_row is not None
        user_row.email_confirmed = True
        session.commit()

    # 2. Login to get first token
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "pwdchange@example.com", "password": "OldPassword123!"},
    )
    token1 = login_resp.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Wait 1s so iat is strictly earlier than password_changed_at
    time.sleep(1.1)

    # 3. Change password
    change_resp = client.post(
        "/api/v1/auth/change-password",
        headers=headers1,
        json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
    )
    assert change_resp.status_code == 200

    # 4. Attempt to use old token1 -> 401
    me_resp = client.get("/api/v1/auth/me", headers=headers1)
    assert me_resp.status_code == 401
