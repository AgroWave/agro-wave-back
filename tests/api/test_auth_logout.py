"""API tests for logout flow (AC-01-05)."""

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agrowave.modules.identity.infrastructure.row_models import (
    IdentityRevokedTokenRow,
    IdentityUserRow,
)


def test_ac01_05_logout_revokes_token(client: TestClient, api_engine) -> None:
    # 1. Register & activate user
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@example.com",
            "name": "Logout User",
            "password": "Password123!",
        },
    )
    with Session(api_engine) as session:
        statement = select(IdentityUserRow).where(
            IdentityUserRow.email == "logout_test@example.com"
        )
        user_row = session.exec(statement).first()
        assert user_row is not None
        user_row.email_confirmed = True
        session.commit()

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "logout_test@example.com", "password": "Password123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Logout
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200

    # 4. Check DB that revoked token row exists
    with Session(api_engine) as session:
        statement_rev = select(IdentityRevokedTokenRow)
        revoked_rows = list(session.exec(statement_rev).all())
        assert len(revoked_rows) >= 1

    # 5. Subsequent request fails with 401
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 401
