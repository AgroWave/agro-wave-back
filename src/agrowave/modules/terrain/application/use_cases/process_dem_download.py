"""Background processing use case for downloading and storing DEM files."""

import contextlib
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from agrowave.modules.terrain.domain.models import DemStatus
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemRepository,
    ElevationSource,
)


@dataclass(frozen=True)
class ProcessDemDownloadCommand:
    """Command to execute asynchronous DEM download and processing.

    Attributes:
        dem_id: Identifier of the pending DEM entity.
    """

    dem_id: UUID


class ProcessDemDownload:
    """Worker use case that fetches tiles, builds COG, and persists in object storage."""

    def __init__(
        self,
        repo: DemRepository,
        elevation_source: ElevationSource,
        object_store: DemObjectStore,
        temp_dir: Path | None = None,
    ) -> None:
        """Initializes the background download processor.

        Args:
            repo: Port for persisting DEM state.
            elevation_source: Port for retrieving and mosaicking elevation data.
            object_store: Port for uploading raster files to S3/MinIO.
            temp_dir: Optional custom temporary working directory.
        """
        self._repo = repo
        self._elevation_source = elevation_source
        self._object_store = object_store
        self._temp_dir = temp_dir

    def execute(self, command: ProcessDemDownloadCommand) -> None:
        """Downloads raster data, generates COG, and updates DEM status to AVAILABLE or FAILED.

        Args:
            command: Command containing target DEM identifier.
        """
        dem = self._repo.get_by_id(command.dem_id)
        if dem is None:
            return

        target_dir = self._temp_dir or Path(tempfile.gettempdir())
        tmp_cog_path = target_dir / f"cog_{dem.id}.tif"

        try:
            size_bytes, resolution_m = self._elevation_source.download_and_mosaic(
                bounds=dem.bounds,
                output_cog_path=tmp_cog_path,
            )

            object_key = f"dems/{dem.id}.tif"
            self._object_store.upload_file(key=object_key, file_path=tmp_cog_path)

            dem.status = DemStatus.AVAILABLE
            dem.object_key = object_key
            dem.size_bytes = size_bytes
            dem.resolution_m = resolution_m
            dem.failure_reason = None
            dem.updated_at = datetime.now(UTC)
            self._repo.save(dem)
        except Exception as exc:
            dem.status = DemStatus.FAILED
            dem.failure_reason = str(exc)
            dem.updated_at = datetime.now(UTC)
            self._repo.save(dem)
        finally:
            if tmp_cog_path.exists():
                with contextlib.suppress(OSError):
                    tmp_cog_path.unlink()
