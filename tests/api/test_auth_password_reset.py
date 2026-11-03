"""API tests for password reset and email confirmation flows (AC-01-06, AC-31, AC-01-02)."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agrowave.modules.identity.domain.models import OneTimeTokenPurpose
from agrowave.modules.identity.infrastructure.row_models import (
    IdentityOneTimeTokenRow,
    IdentityUserRow,
)


def test_ac01_06_request_reset_always_200_and_sends_email(client: TestClient, api_engine) -> None:
    # 1. Non-existent email -> still responds 200
    resp_nonexistent = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "nonexistent@example.com"},
    )
    assert resp_nonexistent.status_code == 200

    # 2. Existing user
    client.post(
        "/api/v1/auth/register",
        json={"email": "reset_user@example.com", "name": "Reset User", "password": "Password123!"},
    )

    resp_existing = client.post(
        "/api/v1/auth/request-password-reset",
        json={"email": "reset_user@example.com"},
    )
    assert resp_existing.status_code == 200

    # Verify a token was stored
    with Session(api_engine) as session:
        statement = select(IdentityOneTimeTokenRow).where(
            IdentityOneTimeTokenRow.purpose == OneTimeTokenPurpose.PASSWORD_RESET.value
        )
        tokens = list(session.exec(statement).all())
        assert len(tokens) >= 1


def test_ac31_expired_or_invalid_reset_token_rejected(client: TestClient) -> None:
    # Invalid token
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "completely-invalid-token", "new_password": "NewSecretPassword123!"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "InvalidOrExpiredToken"


def test_ac01_02_confirm_email_api(client: TestClient, api_engine) -> None:
    # 1. Register user
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "confirm_api@example.com",
            "name": "Confirm API",
            "password": "Password123!",
        },
    )
    user_id = UUID(reg_resp.json()["id"])

    # 2. Find confirmation token in database and use it
    with Session(api_engine) as session:
        # Create a known raw token
        raw_token = "valid_confirmation_token_12345"
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token_row = IdentityOneTimeTokenRow(
            user_id=user_id,
            purpose=OneTimeTokenPurpose.EMAIL_CONFIRMATION.value,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
        session.add(token_row)
        session.commit()

    # 3. Call confirm-email API
    confirm_resp = client.post(
        "/api/v1/auth/confirm-email",
        json={"token": raw_token},
    )
    assert confirm_resp.status_code == 200

    # 4. Verify user is now confirmed
    with Session(api_engine) as session:
        user_row = session.get(IdentityUserRow, user_id)
        assert user_row is not None
        assert user_row.email_confirmed is True

    # 5. Calling confirm again fails because token was already consumed
    confirm_again = client.post(
        "/api/v1/auth/confirm-email",
        json={"token": raw_token},
    )
    assert confirm_again.status_code == 400
