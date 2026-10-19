"""Fixtures for integration tests against the PostgreSQL and MinIO services of compose.yaml.

The test database (``TEST_DATABASE_URL``) and test bucket (``TEST_S3_BUCKET_DEMS``) are
separate from the development ones; these fixtures create and empty them.
"""

import os
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError


def _require_env(name: str) -> str:
    """Return an environment variable or fail loudly; integration tests are never skipped."""
    value = os.environ.get(name)
    if not value:
        pytest.fail(f"{name} must be set to run integration tests (see .env.example)")
    return value


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """URL of the dedicated integration-test database."""
    return _require_env("TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def s3_client() -> Any:
    """Boto3 S3 client pointed at the MinIO service."""
    return boto3.client(
        "s3",
        endpoint_url=_require_env("S3_ENDPOINT_URL"),
        aws_access_key_id=_require_env("S3_ACCESS_KEY"),
        aws_secret_access_key=_require_env("S3_SECRET_KEY"),
        region_name=_require_env("S3_REGION"),
    )


def _drop_bucket(client: Any, bucket: str) -> None:
    """Delete every object in the bucket and then the bucket itself, if it exists."""
    try:
        objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            return
        raise
    for item in objects:
        client.delete_object(Bucket=bucket, Key=item["Key"])
    client.delete_bucket(Bucket=bucket)


@pytest.fixture
def missing_test_bucket(s3_client: Any) -> Iterator[str]:
    """Name of the test bucket, guaranteed not to exist before the test and removed after it."""
    bucket = _require_env("TEST_S3_BUCKET_DEMS")
    _drop_bucket(s3_client, bucket)
    yield bucket
    _drop_bucket(s3_client, bucket)
