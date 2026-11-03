"""SQLModel implementation of ProfileRepository."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from agrowave.modules.profiles.domain.models import Band, LpwanProfile, Technology
from agrowave.modules.profiles.domain.ports import ProfileRepository
from agrowave.modules.profiles.infrastructure.row_models import (
    ProfilesLpwanProfileRow,
    ProfilesProfileBandRow,
)


class SqlModelProfileRepository(ProfileRepository):
    """PostgreSQL/SQLModel implementation of ProfileRepository."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def _to_entity(self, row: ProfilesLpwanProfileRow) -> LpwanProfile:
        """Converts database row model to domain entity."""
        return LpwanProfile(
            id=row.id,
            name=row.name,
            technology=Technology(row.technology),
            reference_sensitivity_dbm=row.reference_sensitivity_dbm,
            bands=[Band(code=b.code, min_mhz=b.min_mhz, max_mhz=b.max_mhz) for b in row.bands],
            spreading_factor=row.spreading_factor,
            owner_id=row.owner_id,
            is_predefined=row.is_predefined,
            created_at=row.created_at,
        )

    def get_by_id(self, profile_id: UUID) -> LpwanProfile | None:
        """Retrieves profile by identifier."""
        with Session(self._engine) as session:
            stmt = select(ProfilesLpwanProfileRow).where(ProfilesLpwanProfileRow.id == profile_id)
            row = session.exec(stmt).first()
            if row is None:
                return None
            return self._to_entity(row)

    def list_accessible(
        self,
        user_id: UUID,
        technology: Technology | None = None,
        owner: str | None = None,
    ) -> list[LpwanProfile]:
        """Lists predefined profiles and profiles owned by the specified user."""
        with Session(self._engine) as session:
            stmt = select(ProfilesLpwanProfileRow)

            if owner == "mine":
                stmt = stmt.where(ProfilesLpwanProfileRow.owner_id == user_id)
            elif owner == "predefined":
                stmt = stmt.where(col(ProfilesLpwanProfileRow.is_predefined).is_(True))
            else:
                stmt = stmt.where(
                    (col(ProfilesLpwanProfileRow.is_predefined).is_(True))
                    | (ProfilesLpwanProfileRow.owner_id == user_id)
                )

            if technology is not None:
                stmt = stmt.where(ProfilesLpwanProfileRow.technology == technology.value)

            stmt = stmt.order_by(
                col(ProfilesLpwanProfileRow.is_predefined).desc(),
                col(ProfilesLpwanProfileRow.name).asc(),
            )
            rows = session.exec(stmt).all()
            return [self._to_entity(row) for row in rows]

    def save(self, profile: LpwanProfile) -> None:
        """Persists or updates an LPWAN profile and its bands."""
        with Session(self._engine) as session:
            existing = session.get(ProfilesLpwanProfileRow, profile.id)
            if existing is None:
                row = ProfilesLpwanProfileRow(
                    id=profile.id,
                    owner_id=profile.owner_id,
                    is_predefined=profile.is_predefined,
                    name=profile.name,
                    technology=profile.technology.value,
                    spreading_factor=profile.spreading_factor,
                    reference_sensitivity_dbm=profile.reference_sensitivity_dbm,
                    created_at=profile.created_at or datetime.now(UTC),
                )
                session.add(row)
                session.flush()

                for band in profile.bands:
                    session.add(
                        ProfilesProfileBandRow(
                            profile_id=profile.id,
                            code=band.code,
                            min_mhz=band.min_mhz,
                            max_mhz=band.max_mhz,
                        )
                    )
            else:
                existing.name = profile.name
                existing.technology = profile.technology.value
                existing.spreading_factor = profile.spreading_factor
                existing.reference_sensitivity_dbm = profile.reference_sensitivity_dbm
                existing.owner_id = profile.owner_id
                existing.is_predefined = profile.is_predefined

                # Delete old bands and add updated ones
                existing_bands = session.exec(
                    select(ProfilesProfileBandRow).where(
                        ProfilesProfileBandRow.profile_id == profile.id
                    )
                ).all()
                for eb in existing_bands:
                    session.delete(eb)
                session.flush()

                for band in profile.bands:
                    session.add(
                        ProfilesProfileBandRow(
                            profile_id=profile.id,
                            code=band.code,
                            min_mhz=band.min_mhz,
                            max_mhz=band.max_mhz,
                        )
                    )

            session.commit()

    def delete(self, profile_id: UUID) -> None:
        """Deletes a profile by identifier."""
        with Session(self._engine) as session:
            existing = session.get(ProfilesLpwanProfileRow, profile_id)
            if existing is not None:
                session.delete(existing)
                session.commit()
