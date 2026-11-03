"""Application configuration loaded from environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for the AGROWAVE application.

    Attributes:
        database_url: Database connection URL for PostgreSQL.
        s3_endpoint_url: S3 endpoint URL for MinIO in dev or cloud in production.
        s3_bucket_dems: Target S3 bucket name for storing DEM objects.
        s3_access_key: Access key for S3 compatible store.
        s3_secret_key: Secret key for S3 compatible store.
        s3_region: Region identifier for S3 compatible store.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    s3_endpoint_url: str
    s3_bucket_dems: str = "agrowave-dems"
    s3_access_key: SecretStr
    s3_secret_key: SecretStr
    s3_region: str = "us-east-1"
    jwt_secret_key: SecretStr = SecretStr(
        "development-jwt-secret-key-change-in-production-min-32-chars"
    )
    jwt_algorithm: str = "HS256"


def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()
