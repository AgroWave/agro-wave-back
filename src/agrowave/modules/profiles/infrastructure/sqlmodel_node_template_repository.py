"""SQLModel implementation of NodeTemplateRepository."""

from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from agrowave.modules.profiles.domain.models import (
    Antenna,
    NodeRole,
    NodeTemplate,
    Polarization,
    Technology,
    TxPower,
)
from agrowave.modules.profiles.domain.ports import NodeTemplateRepository
from agrowave.modules.profiles.infrastructure.row_models import ProfilesNodeTemplateRow


class SqlModelNodeTemplateRepository(NodeTemplateRepository):
    """PostgreSQL/SQLModel implementation of NodeTemplateRepository."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def _to_entity(self, row: ProfilesNodeTemplateRow) -> NodeTemplate:
        """Converts database row model to domain entity."""
        polarization = Polarization(row.polarization) if row.polarization is not None else None
        tx_power = (
            TxPower(
                nominal_dbm=row.tx_power_nominal_dbm,
                tolerance_db=row.tx_power_tolerance_db or 0.0,
            )
            if row.tx_power_nominal_dbm is not None
            else None
        )
        antenna = Antenna(
            reference=row.antenna_ref,
            gain_dbi=row.antenna_gain_dbi,
            polarization=polarization,
        )
        return NodeTemplate(
            id=row.id,
            technology=Technology(row.technology),
            role=NodeRole(row.role),
            name=row.name,
            module_ref=row.module_ref,
            antenna=antenna,
            tx_power=tx_power,
        )

    def list_by_technology(self, technology: Technology) -> list[NodeTemplate]:
        """Lists node templates for the specified technology."""
        with Session(self._engine) as session:
            stmt = (
                select(ProfilesNodeTemplateRow)
                .where(ProfilesNodeTemplateRow.technology == technology.value)
                .order_by(
                    col(ProfilesNodeTemplateRow.role).asc(),
                    col(ProfilesNodeTemplateRow.name).asc(),
                )
            )
            rows = session.exec(stmt).all()
            return [self._to_entity(row) for row in rows]

    def get_by_id(self, template_id: UUID) -> NodeTemplate | None:
        """Retrieves template by identifier."""
        with Session(self._engine) as session:
            row = session.get(ProfilesNodeTemplateRow, template_id)
            if row is None:
                return None
            return self._to_entity(row)
