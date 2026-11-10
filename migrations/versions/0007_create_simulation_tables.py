"""Create simulation tables.

Revision ID: 0007_simulation_tables
Revises: 0006_scenarios_tables
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_simulation_tables"
down_revision: str | None = "0006_scenarios_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_simulation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("comparison_group_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("technology", sa.String(), nullable=False),
        sa.Column("propagation_model_id", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("viable_links_pct", sa.Float(), nullable=True),
        sa.Column("min_margin_db", sa.Float(), nullable=True),
        sa.Column("mean_margin_db", sa.Float(), nullable=True),
        sa.Column("fresnel_clear_count", sa.Integer(), nullable=True),
        sa.Column("fresnel_marginal_count", sa.Integer(), nullable=True),
        sa.Column("fresnel_obstructed_count", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["identity_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_simulation_comparison_group_id",
        "simulation_simulation",
        ["comparison_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_simulation_owner_id",
        "simulation_simulation",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_simulation_scenario_id",
        "simulation_simulation",
        ["scenario_id"],
        unique=False,
    )
    op.create_index(
        "ix_simulation_simulation_status",
        "simulation_simulation",
        ["status"],
        unique=False,
    )

    op.create_table(
        "simulation_link_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("link_id", sa.Uuid(), nullable=False),
        sa.Column("end_node_name", sa.String(), nullable=False),
        sa.Column("access_node_name", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=False),
        sa.Column("fresnel_min_ratio", sa.Float(), nullable=False),
        sa.Column("fresnel_min_at_m", sa.Float(), nullable=False),
        sa.Column("fresnel_max_radius_m", sa.Float(), nullable=False),
        sa.Column("fresnel_verdict", sa.String(), nullable=False),
        sa.Column("free_space_loss_db", sa.Float(), nullable=False),
        sa.Column("received_power_dbm", sa.Float(), nullable=False),
        sa.Column("sensitivity_used_dbm", sa.Float(), nullable=False),
        sa.Column("sensitivity_origin", sa.String(), nullable=False),
        sa.Column("margin_db", sa.Float(), nullable=False),
        sa.Column("viable", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulation_simulation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_link_result_simulation_id",
        "simulation_link_result",
        ["simulation_id"],
        unique=False,
    )

    op.create_table(
        "simulation_path_loss_quantile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("link_result_id", sa.Uuid(), nullable=False),
        sa.Column("reliability_pct", sa.Float(), nullable=False),
        sa.Column("confidence_pct", sa.Float(), nullable=False),
        sa.Column("loss_db", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_result_id"],
            ["simulation_link_result.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_path_loss_quantile_link_result_id",
        "simulation_path_loss_quantile",
        ["link_result_id"],
        unique=False,
    )

    op.create_table(
        "simulation_link_profile",
        sa.Column("link_result_id", sa.Uuid(), nullable=False),
        sa.Column("series", sa.JSON(), nullable=False),
        sa.Column("series_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_result_id"],
            ["simulation_link_result.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("link_result_id"),
    )

    op.create_table(
        "simulation_warning",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_id", sa.Uuid(), nullable=False),
        sa.Column("link_result_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulation_simulation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_warning_simulation_id",
        "simulation_warning",
        ["simulation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_simulation_warning_simulation_id", table_name="simulation_warning")
    op.drop_table("simulation_warning")

    op.drop_table("simulation_link_profile")

    op.drop_index(
        "ix_simulation_path_loss_quantile_link_result_id",
        table_name="simulation_path_loss_quantile",
    )
    op.drop_table("simulation_path_loss_quantile")

    op.drop_index("ix_simulation_link_result_simulation_id", table_name="simulation_link_result")
    op.drop_table("simulation_link_result")

    op.drop_index("ix_simulation_simulation_status", table_name="simulation_simulation")
    op.drop_index("ix_simulation_simulation_scenario_id", table_name="simulation_simulation")
    op.drop_index("ix_simulation_simulation_owner_id", table_name="simulation_simulation")
    op.drop_index(
        "ix_simulation_simulation_comparison_group_id",
        table_name="simulation_simulation",
    )
    op.drop_table("simulation_simulation")
