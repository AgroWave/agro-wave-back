"""Create identity tables (identity_user, identity_one_time_token, identity_revoked_token).

Revision ID: 0001_identity
Revises: None
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_identity"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. identity_user
    op.create_table(
        "identity_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("email_confirmed", sa.Boolean(), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_identity_user_email"), "identity_user", ["email"], unique=True)

    # 2. identity_one_time_token
    op.create_table(
        "identity_one_time_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["identity_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_identity_one_time_token_token_hash"),
        "identity_one_time_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_identity_one_time_token_user_id"),
        "identity_one_time_token",
        ["user_id"],
        unique=False,
    )

    # 3. identity_revoked_token
    op.create_table(
        "identity_revoked_token",
        sa.Column("jti", sa.String(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["identity_user.id"]),
        sa.PrimaryKeyConstraint("jti"),
    )


def downgrade() -> None:
    op.drop_table("identity_revoked_token")
    op.drop_index(op.f("ix_identity_one_time_token_user_id"), table_name="identity_one_time_token")
    op.drop_index(
        op.f("ix_identity_one_time_token_token_hash"), table_name="identity_one_time_token"
    )
    op.drop_table("identity_one_time_token")
    op.drop_index(op.f("ix_identity_user_email"), table_name="identity_user")
    op.drop_table("identity_user")
