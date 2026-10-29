"""SQLModel implementation of UserRepository."""

from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from agrowave.modules.identity.domain.models import Role, User
from agrowave.modules.identity.domain.ports import UserRepository
from agrowave.modules.identity.infrastructure.row_models import IdentityUserRow


class SqlModelUserRepository(UserRepository):
    """Adapter implementing UserRepository port backed by PostgreSQL / SQLModel."""

    def __init__(self, engine: Engine) -> None:
        """Initializes the repository with a database engine.

        Args:
            engine: SQLAlchemy/SQLModel database engine.
        """
        self._engine = engine

    def _to_entity(self, row: IdentityUserRow) -> User:
        return User(
            id=row.id,
            email=row.email,
            name=row.name,
            password_hash=row.password_hash,
            role=Role(row.role),
            email_confirmed=row.email_confirmed,
            password_changed_at=row.password_changed_at,
            created_at=row.created_at,
        )

    def find_by_id(self, user_id: UUID) -> User | None:
        """Finds a user by id."""
        with Session(self._engine) as session:
            row = session.get(IdentityUserRow, user_id)
            return self._to_entity(row) if row else None

    def find_by_email(self, email: str) -> User | None:
        """Finds a user by email (case-insensitive lookup)."""
        with Session(self._engine) as session:
            statement = select(IdentityUserRow).where(IdentityUserRow.email == email.lower())
            row = session.exec(statement).first()
            return self._to_entity(row) if row else None

    def save(self, user: User) -> None:
        """Saves or updates a user entity."""
        with Session(self._engine) as session:
            row = session.get(IdentityUserRow, user.id)
            if row is None:
                row = IdentityUserRow(
                    id=user.id,
                    email=user.email.lower(),
                    name=user.name,
                    password_hash=user.password_hash,
                    role=user.role.value,
                    email_confirmed=user.email_confirmed,
                    password_changed_at=user.password_changed_at,
                    created_at=user.created_at,
                )
                session.add(row)
            else:
                row.email = user.email.lower()
                row.name = user.name
                row.password_hash = user.password_hash
                row.role = user.role.value
                row.email_confirmed = user.email_confirmed
                row.password_changed_at = user.password_changed_at
            session.commit()
