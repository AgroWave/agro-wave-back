"""Create scenarios tables.

Revision ID: 0006_scenarios_tables
Revises: 0005_terrain_tables
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_scenarios_tables"
down_revision: str | None = "0005_terrain_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenarios_scenario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("comparison_group_id", sa.Uuid(), nullable=False),
        sa.Column("south", sa.Float(), nullable=False),
        sa.Column("west", sa.Float(), nullable=False),
        sa.Column("north", sa.Float(), nullable=False),
        sa.Column("east", sa.Float(), nullable=False),
        sa.Column("dem_id", sa.Uuid(), nullable=True),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("technology", sa.String(), nullable=True),
        sa.Column("band_code", sa.String(), nullable=True),
        sa.Column("frequency_mhz", sa.Float(), nullable=True),
        sa.Column("propagation_model_id", sa.String(), nullable=True),
        sa.Column("propagation_params", sa.JSON(), nullable=True),
        sa.Column("propagation_params_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dem_id"], ["terrain_dem.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["identity_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles_lpwan_profile.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenarios_scenario_comparison_group_id",
        "scenarios_scenario",
        ["comparison_group_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenarios_scenario_dem_id",
        "scenarios_scenario",
        ["dem_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenarios_scenario_owner_id",
        "scenarios_scenario",
        ["owner_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenarios_scenario_profile_id",
        "scenarios_scenario",
        ["profile_id"],
        unique=False,
    )

    op.create_table(
        "scenarios_access_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("height_agl_m", sa.Float(), nullable=False),
        sa.Column("antenna_ref", sa.String(), nullable=True),
        sa.Column("antenna_gain_dbi", sa.Float(), nullable=False),
        sa.Column("polarization", sa.String(), nullable=True),
        sa.Column("sensitivity_dbm", sa.Float(), nullable=False),
        sa.Column("sensitivity_origin", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios_scenario.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenarios_access_node_scenario_id",
        "scenarios_access_node",
        ["scenario_id"],
        unique=False,
    )

    op.create_table(
        "scenarios_end_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("height_agl_m", sa.Float(), nullable=False),
        sa.Column("antenna_ref", sa.String(), nullable=True),
        sa.Column("antenna_gain_dbi", sa.Float(), nullable=False),
        sa.Column("polarization", sa.String(), nullable=True),
        sa.Column("tx_power_nominal_dbm", sa.Float(), nullable=False),
        sa.Column("tx_power_tolerance_db", sa.Float(), nullable=False),
        sa.Column("source_template_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios_scenario.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scenarios_end_node_scenario_id",
        "scenarios_end_node",
        ["scenario_id"],
        unique=False,
    )

    op.create_table(
        "scenarios_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scenario_id", sa.Uuid(), nullable=False),
        sa.Column("end_node_id", sa.Uuid(), nullable=False),
        sa.Column("access_node_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["access_node_id"],
            ["scenarios_access_node.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["end_node_id"],
            ["scenarios_end_node.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios_scenario.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("end_node_id"),
    )
    op.create_index(
        "ix_scenarios_link_access_node_id",
        "scenarios_link",
        ["access_node_id"],
        unique=False,
    )
    op.create_index(
        "ix_scenarios_link_scenario_id",
        "scenarios_link",
        ["scenario_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scenarios_link_scenario_id", table_name="scenarios_link")
    op.drop_index("ix_scenarios_link_access_node_id", table_name="scenarios_link")
    op.drop_table("scenarios_link")

    op.drop_index("ix_scenarios_end_node_scenario_id", table_name="scenarios_end_node")
    op.drop_table("scenarios_end_node")

    op.drop_index("ix_scenarios_access_node_scenario_id", table_name="scenarios_access_node")
    op.drop_table("scenarios_access_node")

    op.drop_index("ix_scenarios_scenario_profile_id", table_name="scenarios_scenario")
    op.drop_index("ix_scenarios_scenario_owner_id", table_name="scenarios_scenario")
    op.drop_index("ix_scenarios_scenario_dem_id", table_name="scenarios_scenario")
    op.drop_index("ix_scenarios_scenario_comparison_group_id", table_name="scenarios_scenario")
    op.drop_table("scenarios_scenario")
