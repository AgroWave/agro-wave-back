"""Seed unsourced node template values as NULL.

The parameter table (radio-and-propagation.md) has no access node for NB-IoT and LTE-M,
so their antenna gain and module are pending (NULL) instead of placeholder values.

Revision ID: 0004_profiles_unsourced
Revises: 0003_profiles_seed
Create Date: 2026-11-02
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0004_profiles_unsourced"
down_revision: str | None = "0003_profiles_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEMPLATE_NBIOT_ACCESS_NODE = UUID("00000000-0000-0000-0002-000000000002")
TEMPLATE_LTEM_ACCESS_NODE = UUID("00000000-0000-0000-0003-000000000002")


def upgrade() -> None:
    """Allow a NULL antenna gain and clear placeholder values of the access node templates."""
    op.alter_column(
        "profiles_node_template", "antenna_gain_dbi", existing_type=sa.Float(), nullable=True
    )
    for template_id, name in (
        (TEMPLATE_NBIOT_ACCESS_NODE, "NB-IoT access node"),
        (TEMPLATE_LTEM_ACCESS_NODE, "LTE-M access node"),
    ):
        op.execute(
            sa.text(
                "UPDATE profiles_node_template "
                "SET name = :name, module_ref = NULL, antenna_gain_dbi = NULL "
                "WHERE id = :id"
            ).bindparams(sa.bindparam("id", template_id, type_=sa.Uuid), name=name)
        )


def downgrade() -> None:
    """Restore the previous placeholder values and the NOT NULL constraint."""
    for template_id, name in (
        (TEMPLATE_NBIOT_ACCESS_NODE, "Generic NB-IoT Base Station"),
        (TEMPLATE_LTEM_ACCESS_NODE, "Generic LTE-M Base Station"),
    ):
        op.execute(
            sa.text("UPDATE profiles_node_template SET name = :name WHERE id = :id").bindparams(
                name=name, id=template_id
            )
        )
    op.execute(
        "UPDATE profiles_node_template SET antenna_gain_dbi = 0.0 WHERE antenna_gain_dbi IS NULL"
    )
    op.alter_column(
        "profiles_node_template", "antenna_gain_dbi", existing_type=sa.Float(), nullable=False
    )
