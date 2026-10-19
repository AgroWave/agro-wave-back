"""Object store bootstrap: the DEM bucket is created idempotently at startup (AC-00-06)."""

from typing import Any

import pytest

from agrowave.shared.infrastructure.object_store_bootstrap import ensure_bucket

pytestmark = pytest.mark.integration


def test_ac00_06_ensure_bucket_is_idempotent(s3_client: Any, missing_test_bucket: str) -> None:
    created_first = ensure_bucket(s3_client, missing_test_bucket)
    s3_client.put_object(Bucket=missing_test_bucket, Key="probe.txt", Body=b"keep me")

    created_second = ensure_bucket(s3_client, missing_test_bucket)

    assert created_first is True, "first call must create the missing bucket"
    assert created_second is False, "second call must detect the existing bucket"
    body = s3_client.get_object(Bucket=missing_test_bucket, Key="probe.txt")["Body"].read()
    assert body == b"keep me", "second call must not alter the existing bucket"
