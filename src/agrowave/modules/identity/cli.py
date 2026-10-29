"""Administrative command-line interface for the Identity module."""

import argparse
import sys
from collections.abc import Sequence

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from agrowave.modules.identity.domain.models import Role, User
from agrowave.modules.identity.infrastructure.argon2_password_hasher import (
    Argon2PasswordHasher,
)
from agrowave.modules.identity.infrastructure.sqlmodel_user_repository import (
    SqlModelUserRepository,
)
from agrowave.settings import get_settings


def create_admin_command(
    email: str,
    name: str,
    password: str,
    engine: Engine | None = None,
) -> int:
    """Creates or elevates a user to system administrator role (AC-01-08).

    Args:
        email: Email address of the admin user.
        name: Full name of the admin user.
        password: Plain text password for the admin user.
        engine: Optional database engine. If omitted, uses default settings engine.

    Returns:
        0 on success, non-zero on error.
    """
    if engine is None:
        settings = get_settings()
        engine = create_engine(str(settings.database_url))

    hasher = Argon2PasswordHasher()
    repo = SqlModelUserRepository(engine)

    existing_user = repo.find_by_email(email)
    password_hash = hasher.hash(password)

    if existing_user is not None:
        existing_user.role = Role.ADMIN
        existing_user.email_confirmed = True
        existing_user.change_password(password_hash)
        repo.save(existing_user)
        print(f"Existing user '{email}' updated to ADMIN.")
    else:
        admin_user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            role=Role.ADMIN,
            email_confirmed=True,
        )
        repo.save(admin_user)
        print(f"Admin user '{email}' created successfully.")

    return 0


def run_cli(args: Sequence[str] | None = None, engine: Engine | None = None) -> int:
    """Parses command line arguments and invokes administrative subcommands.

    Args:
        args: Sequence of command line arguments, or sys.argv[1:] if None.
        engine: Optional database engine override for testing.

    Returns:
        Integer exit code.
    """
    parser = argparse.ArgumentParser(description="AGROWAVE Identity CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_admin_parser = subparsers.add_parser(
        "create-admin", help="Create or elevate a user to ADMIN"
    )
    create_admin_parser.add_argument("--email", required=True, help="Administrator email address")
    create_admin_parser.add_argument(
        "--name", required=True, help="Administrator full display name"
    )
    create_admin_parser.add_argument(
        "--password", required=True, help="Administrator plain text password"
    )

    parsed = parser.parse_args(args)

    if parsed.command == "create-admin":
        return create_admin_command(
            email=parsed.email,
            name=parsed.name,
            password=parsed.password,
            engine=engine,
        )

    return 1


def main() -> None:
    """CLI entry point for python -m agrowave.modules.identity.cli."""
    sys.exit(run_cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
