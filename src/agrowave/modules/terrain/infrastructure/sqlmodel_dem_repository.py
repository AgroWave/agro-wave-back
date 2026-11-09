"""SQLModel implementation of DemRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from agrowave.modules.terrain.domain.models import Bounds, Dem, DemStatus
from agrowave.modules.terrain.domain.ports import DemRepository
from agrowave.modules.terrain.infrastructure.row_models import TerrainDemRow


class SqlModelDemRepository(DemRepository):
    """PostgreSQL/SQLModel implementation of DemRepository."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def _to_entity(self, row: TerrainDemRow) -> Dem:
        """Converts database row model to domain entity."""
        return Dem(
            id=row.id,
            owner_id=row.owner_id,
            name=row.name,
            description=row.description,
            bounds=Bounds(
                south=row.south,
                west=row.west,
                north=row.north,
                east=row.east,
            ),
            status=DemStatus(row.status),
            resolution_m=row.resolution_m,
            object_key=row.object_key,
            size_bytes=row.size_bytes,
            failure_reason=row.failure_reason,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def get_by_id(self, dem_id: UUID) -> Dem | None:
        """Retrieves a DEM by identifier."""
        with Session(self._engine) as session:
            row = session.get(TerrainDemRow, dem_id)
            if row is None:
                return None
            return self._to_entity(row)

    def list_by_owner(self, owner_id: UUID, search: str | None = None) -> list[Dem]:
        """Lists DEMs owned by a user, optionally filtered by name search."""
        with Session(self._engine) as session:
            stmt = select(TerrainDemRow).where(TerrainDemRow.owner_id == owner_id)

            if search:
                pattern = f"%{search.strip()}%"
                stmt = stmt.where(
                    col(TerrainDemRow.name).ilike(pattern)
                    | col(TerrainDemRow.description).ilike(pattern)
                )

            stmt = stmt.order_by(col(TerrainDemRow.created_at).desc())
            rows = session.exec(stmt).all()
            return [self._to_entity(r) for r in rows]

    def save(self, dem: Dem) -> None:
        """Persists or updates a DEM entity."""
        with Session(self._engine) as session:
            row = session.get(TerrainDemRow, dem.id)
            now = datetime.now(UTC)
            if row is None:
                row = TerrainDemRow(
                    id=dem.id,
                    owner_id=dem.owner_id,
                    name=dem.name,
                    description=dem.description,
                    south=dem.bounds.south,
                    west=dem.bounds.west,
                    north=dem.bounds.north,
                    east=dem.bounds.east,
                    status=dem.status.value,
                    resolution_m=dem.resolution_m,
                    object_key=dem.object_key,
                    size_bytes=dem.size_bytes,
                    failure_reason=dem.failure_reason,
                    created_at=dem.created_at or now,
                    updated_at=dem.updated_at or now,
                )
                session.add(row)
            else:
                row.name = dem.name
                row.description = dem.description
                row.south = dem.bounds.south
                row.west = dem.bounds.west
                row.north = dem.bounds.north
                row.east = dem.bounds.east
                row.status = dem.status.value
                row.resolution_m = dem.resolution_m
                row.object_key = dem.object_key
                row.size_bytes = dem.size_bytes
                row.failure_reason = dem.failure_reason
                row.updated_at = now

            session.commit()

    def delete(self, dem_id: UUID) -> None:
        """Deletes a DEM record by identifier."""
        with Session(self._engine) as session:
            row = session.get(TerrainDemRow, dem_id)
            if row is not None:
                session.delete(row)
                session.commit()

