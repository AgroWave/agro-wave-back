"""Create terrain tables (terrain_dem).

Revision ID: 0005_terrain_tables
Revises: 0004_profiles_unsourced
Create Date: 2026-11-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_terrain_tables"
down_revision: str | None = "0004_profiles_unsourced"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "terrain_dem",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("south", sa.Float(), nullable=False),
        sa.Column("west", sa.Float(), nullable=False),
        sa.Column("north", sa.Float(), nullable=False),
        sa.Column("east", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resolution_m", sa.Float(), nullable=False, server_default=sa.text("30.0")),
        sa.Column("object_key", sa.String(), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["identity_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_terrain_dem_owner_id",
        "terrain_dem",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_terrain_dem_status",
        "terrain_dem",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_terrain_dem_status", table_name="terrain_dem")
    op.drop_index("ix_terrain_dem_owner_id", table_name="terrain_dem")
    op.drop_table("terrain_dem")
