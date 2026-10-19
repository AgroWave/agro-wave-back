"""Bootstrap script executed at container startup."""

import logging
import sys

import boto3
from alembic import command
from alembic.config import Config

from agrowave.settings import Settings
from agrowave.shared.infrastructure.object_store_bootstrap import ensure_bucket

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agrowave.bootstrap")


def run_migrations(settings: Settings) -> None:
    """Applies pending Alembic database migrations up to head.

    Args:
        settings: Application configuration settings.
    """
    logger.info("Applying database migrations to head...")
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")
    logger.info("Database migrations successfully applied.")


def bootstrap_object_store(settings: Settings) -> None:
    """Ensures required S3 buckets exist in the object storage backend.

    Args:
        settings: Application configuration settings.
    """
    logger.info("Ensuring object store bucket '%s' exists...", settings.s3_bucket_dems)
    s3_client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
    )
    created = ensure_bucket(s3_client, settings.s3_bucket_dems)
    if created:
        logger.info("Bucket '%s' was created.", settings.s3_bucket_dems)
    else:
        logger.info("Bucket '%s' already exists.", settings.s3_bucket_dems)


def main() -> None:
    """Runs the application initialization sequence."""
    settings = Settings()
    try:
        run_migrations(settings)
        bootstrap_object_store(settings)
    except Exception as exc:
        logger.error("Bootstrap failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
