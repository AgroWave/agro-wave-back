"""Rasterio-based adapter for extracting terrain elevation profiles from COG DEMs (ADR-07)."""

import math
from urllib.parse import urlparse
from uuid import UUID

import boto3
import rasterio
from rasterio.env import Env
from rasterio.io import MemoryFile
from rasterio.session import AWSSession

from agrowave.modules.simulation.domain.errors import TerrainProfileExtractionError
from agrowave.modules.simulation.domain.ports import SampledTerrainProfile
from agrowave.settings import Settings

MAX_ITM_PROFILE_POINTS = 600


class RasterioTerrainProfileProvider:
    """Extracts elevation profiles from Cloud Optimized GeoTIFFs stored in S3/MinIO (ADR-07)."""

    def __init__(self, settings: Settings) -> None:
        """Initializes the provider with application S3/MinIO settings."""
        self._settings = settings

    def extract_profile(
        self,
        dem_id: UUID,
        dem_object_key: str | None,
        window_bounds: dict[str, float],
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        distance_m: float,
        resolution_m: float = 30.0,
    ) -> SampledTerrainProfile:
        """Reads elevation samples along the link path from the remote COG.

        Respects the 600-point ITM limit and uses step equal to DEM resolution.

        Args:
            dem_id: Identifier of the DEM.
            dem_object_key: S3 object key of the COG file.
            window_bounds: Study area bounding box dictionary.
            start_lat: End node latitude in decimal degrees.
            start_lng: End node longitude in decimal degrees.
            end_lat: Access node latitude in decimal degrees.
            end_lng: Access node longitude in decimal degrees.
            distance_m: Total horizontal link distance, in meters (m).
            resolution_m: Nominal DEM resolution, in meters (m).

        Returns:
            SampledTerrainProfile containing distances and elevations in meters (m).

        Raises:
            TerrainProfileExtractionError: If the COG is missing or cannot be sampled.
        """
        if not dem_object_key:
            raise TerrainProfileExtractionError(f"DEM '{dem_id}' has no storage object key")

        step_m = max(float(resolution_m), 1.0)
        num_intervals = max(9, int(distance_m / step_m))
        if num_intervals + 1 > MAX_ITM_PROFILE_POINTS:
            num_intervals = MAX_ITM_PROFILE_POINTS - 1
        actual_step_m = distance_m / num_intervals

        distances_m = tuple(round(i * actual_step_m, 2) for i in range(num_intervals + 1))
        coords = [
            (
                end_lng + ((num_intervals - i) / num_intervals) * (start_lng - end_lng),
                end_lat + ((num_intervals - i) / num_intervals) * (start_lat - end_lat),
            )
            for i in range(num_intervals + 1)
        ]

        parsed = urlparse(self._settings.s3_endpoint_url)
        host_port = parsed.netloc or parsed.path
        use_https = parsed.scheme == "https"
        clean_key = dem_object_key.lstrip("/")
        vsi_path = f"/vsis3/{self._settings.s3_bucket_dems}/{clean_key}"

        boto_session = boto3.Session(
            aws_access_key_id=self._settings.s3_access_key.get_secret_value(),
            aws_secret_access_key=self._settings.s3_secret_key.get_secret_value(),
            region_name=self._settings.s3_region,
        )
        aws_session = AWSSession(
            session=boto_session,
            endpoint_url=host_port,
            aws_unsigned=False,
        )

        try:
            with (
                Env(
                    session=aws_session,
                    AWS_VIRTUAL_HOSTING="FALSE",
                    AWS_HTTPS="YES" if use_https else "NO",
                    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                ),
                rasterio.open(vsi_path) as dataset,
            ):
                elevations = self._sample_dataset(dataset, coords)
                return SampledTerrainProfile(
                    distances_m=distances_m,
                    elevations_m=elevations,
                    step_m=round(actual_step_m, 2),
                )
        except Exception:
            try:
                s3_client = boto_session.client(
                    "s3",
                    endpoint_url=self._settings.s3_endpoint_url,
                )
                obj = s3_client.get_object(
                    Bucket=self._settings.s3_bucket_dems,
                    Key=clean_key,
                )
                cog_bytes = obj["Body"].read()
                with MemoryFile(cog_bytes) as memfile, memfile.open() as dataset:
                    elevations = self._sample_dataset(dataset, coords)
                    return SampledTerrainProfile(
                        distances_m=distances_m,
                        elevations_m=elevations,
                        step_m=round(actual_step_m, 2),
                    )
            except Exception as exc:
                raise TerrainProfileExtractionError(
                    f"Failed to read COG '{dem_object_key}' from object storage: {exc}"
                ) from exc

    @staticmethod
    def _sample_dataset(
        dataset: rasterio.DatasetReader,
        coords: list[tuple[float, float]],
    ) -> tuple[float, ...]:
        """Samples terrain elevations in meters at the given (lng, lat) coordinates."""
        sampled = list(dataset.sample(coords))
        elevations: list[float] = []
        for val_arr in sampled:
            val = float(val_arr[0])
            if math.isnan(val) or val < -100.0:
                val = 0.0
            elevations.append(round(val, 4))
        return tuple(elevations)
