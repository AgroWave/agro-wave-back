"""Bootstrap utilities for object storage buckets."""

from typing import Any

from botocore.exceptions import ClientError


def ensure_bucket(s3_client: Any, bucket: str) -> bool:
    """Ensures that the given S3 bucket exists, creating it if necessary.

    Args:
        s3_client: Initialized boto3 S3 client.
        bucket: Name of the bucket to ensure.

    Returns:
        True if the bucket was created, False if it already existed.

    Raises:
        ClientError: If an unexpected S3 error occurs during head or creation.
    """
    try:
        s3_client.head_bucket(Bucket=bucket)
        return False
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in ("404", "NoSuchBucket", "NotFound"):
            s3_client.create_bucket(Bucket=bucket)
            return True
        raise
