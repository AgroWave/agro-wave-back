"""Settings: the API loads its configuration from environment variables (AC-00-01)."""

import pytest
from pydantic import ValidationError

from agrowave.settings import Settings

REQUIRED_ENV = {
    "DATABASE_URL": "postgresql+psycopg://user:secret@db:5432/agrowave",
    "S3_ENDPOINT_URL": "http://minio:9000",
    "S3_BUCKET_DEMS": "agrowave-dems",
    "S3_ACCESS_KEY": "access",
    "S3_SECRET_KEY": "secret",
    "S3_REGION": "us-east-1",
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every settings variable inherited from the container environment."""
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_ac00_01_settings_load_from_env(clean_env: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED_ENV.items():
        clean_env.setenv(name, value)

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.database_url == REQUIRED_ENV["DATABASE_URL"]
    assert settings.s3_endpoint_url == REQUIRED_ENV["S3_ENDPOINT_URL"]
    assert settings.s3_bucket_dems == REQUIRED_ENV["S3_BUCKET_DEMS"]
    assert settings.s3_access_key.get_secret_value() == REQUIRED_ENV["S3_ACCESS_KEY"]
    assert settings.s3_secret_key.get_secret_value() == REQUIRED_ENV["S3_SECRET_KEY"]
    assert settings.s3_region == REQUIRED_ENV["S3_REGION"]


def test_ac00_01_missing_database_url_is_rejected(clean_env: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED_ENV.items():
        if name != "DATABASE_URL":
            clean_env.setenv(name, value)

    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)  # type: ignore[call-arg]
