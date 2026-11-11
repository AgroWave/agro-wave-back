"""Add simulation coverage table and DSR evaluation metrics.

Revision ID: 0008_add_simulation_coverage
Revises: 0007_simulation_tables
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_add_simulation_coverage"
down_revision: str | None = "0007_simulation_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add summary columns to simulation_simulation
    op.add_column("simulation_simulation", sa.Column("effective_coverage_area_km2", sa.Float(), nullable=True))
    op.add_column("simulation_simulation", sa.Column("coverage_percentage", sa.Float(), nullable=True))
    op.add_column("simulation_simulation", sa.Column("max_coverage_radius_km", sa.Float(), nullable=True))
    op.add_column("simulation_simulation", sa.Column("variability_index", sa.Float(), nullable=True))

    # 2. Create simulation_coverage_result table
    op.create_table(
        "simulation_coverage_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("access_node_id", sa.Uuid(), nullable=False),
        sa.Column("effective_coverage_area_km2", sa.Float(), nullable=False),
        sa.Column("coverage_percentage", sa.Float(), nullable=False),
        sa.Column("max_coverage_radius_km", sa.Float(), nullable=False),
        sa.Column("variability_index", sa.Float(), nullable=False),
        sa.Column("total_area_km2", sa.Float(), nullable=False),
        sa.Column("covered_samples_count", sa.Integer(), nullable=False),
        sa.Column("total_samples_count", sa.Integer(), nullable=False),
        sa.Column("samples", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulation_simulation.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_coverage_result_simulation_id",
        "simulation_coverage_result",
        ["simulation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_coverage_result_simulation_id", table_name="simulation_coverage_result")
    op.drop_table("simulation_coverage_result")
    op.drop_column("simulation_simulation", "variability_index")
    op.drop_column("simulation_simulation", "max_coverage_radius_km")
    op.drop_column("simulation_simulation", "coverage_percentage")
    op.drop_column("simulation_simulation", "effective_coverage_area_km2")
