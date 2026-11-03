"""Create profiles tables (profiles_lpwan_profile, profiles_profile_band, profiles_node_template).

Revision ID: 0002_profiles_tables
Revises: 0001_identity
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_profiles_tables"
down_revision: str | None = "0001_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. profiles_lpwan_profile
    op.create_table(
        "profiles_lpwan_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("is_predefined", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("technology", sa.String(), nullable=False),
        sa.Column("spreading_factor", sa.Integer(), nullable=True),
        sa.Column("reference_sensitivity_dbm", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profiles_lpwan_profile_owner_id",
        "profiles_lpwan_profile",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_profiles_lpwan_profile_technology",
        "profiles_lpwan_profile",
        ["technology"],
        unique=False,
    )

    # 2. profiles_profile_band
    op.create_table(
        "profiles_profile_band",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("min_mhz", sa.Float(), nullable=True),
        sa.Column("max_mhz", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles_lpwan_profile.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profiles_profile_band_profile_id",
        "profiles_profile_band",
        ["profile_id"],
        unique=False,
    )

    # 3. profiles_node_template
    op.create_table(
        "profiles_node_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("technology", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("module_ref", sa.String(), nullable=True),
        sa.Column("antenna_ref", sa.String(), nullable=True),
        sa.Column("antenna_gain_dbi", sa.Float(), nullable=False),
        sa.Column("polarization", sa.String(), nullable=True),
        sa.Column("tx_power_nominal_dbm", sa.Float(), nullable=True),
        sa.Column("tx_power_tolerance_db", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_profiles_node_template_technology",
        "profiles_node_template",
        ["technology"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_profiles_node_template_technology", table_name="profiles_node_template")
    op.drop_table("profiles_node_template")
    op.drop_index("ix_profiles_profile_band_profile_id", table_name="profiles_profile_band")
    op.drop_table("profiles_profile_band")
    op.drop_index("ix_profiles_lpwan_profile_technology", table_name="profiles_lpwan_profile")
    op.drop_index("ix_profiles_lpwan_profile_owner_id", table_name="profiles_lpwan_profile")
    op.drop_table("profiles_lpwan_profile")
