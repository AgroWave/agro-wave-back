"""S3/MinIO implementation of DemObjectStore."""

import contextlib
from pathlib import Path
from typing import Any

from agrowave.modules.terrain.domain.ports import DemObjectStore


class S3DemObjectStore(DemObjectStore):
    """Stores and deletes raster files in S3-compatible storage."""

    def __init__(self, s3_client: Any, bucket_name: str) -> None:
        """Initializes the object store with an S3 client and target bucket.

        Args:
            s3_client: Boto3 S3 client instance.
            bucket_name: Name of target S3 bucket.
        """
        self._s3 = s3_client
        self._bucket = bucket_name

    def upload_file(self, key: str, file_path: Path) -> None:
        """Uploads a local raster file to object storage.

        Args:
            key: S3 object key.
            file_path: Local filesystem path to the file.
        """
        self._s3.upload_file(str(file_path), self._bucket, key)

    def delete_file(self, key: str) -> None:
        """Removes a raster file from object storage.

        Args:
            key: S3 object key to delete.
        """
        with contextlib.suppress(Exception):
            self._s3.delete_object(Bucket=self._bucket, Key=key)
