"""FABDEM elevation source adapter downloading tiles and producing COG rasters."""

import os
import tempfile
from pathlib import Path

import fabdem
import rasterio

from agrowave.modules.terrain.domain.models import Bounds
from agrowave.modules.terrain.domain.ports import ElevationSource


class FabdemElevationSource(ElevationSource):
    """Downloads FABDEM elevation data and outputs Cloud Optimized GeoTIFFs (RN-25, RN-27)."""

    def __init__(self, cache_dir: Path | str | None = None) -> None:
        """Initializes the elevation source with an optional local cache directory.

        Args:
            cache_dir: Directory path for caching downloaded FABDEM zip/tif tiles.
        """
        self._cache_dir = Path(cache_dir) if cache_dir else None
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def download_and_mosaic(self, bounds: Bounds, output_cog_path: Path) -> tuple[int, float]:
        """Downloads FABDEM tiles, converts them to COG format, and writes to output_cog_path.

        Args:
            bounds: Geographic bounding box (WGS84) to extract.
            output_cog_path: Destination path for the Cloud Optimized GeoTIFF.

        Returns:
            Tuple containing raster size in bytes and resolution in meters (nominal 30.0 m).
        """
        output_cog_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_raw_tif = Path(tmp_dir) / "raw_download.tif"

            # fabdem.download expects (west, south, east, north)
            fabdem.download(
                bounds=(bounds.west, bounds.south, bounds.east, bounds.north),
                output_path=temp_raw_tif,
                show_progress=False,
                cache=self._cache_dir,
            )

            # Convert to Cloud Optimized GeoTIFF with Deflate compression
            with rasterio.open(temp_raw_tif) as src:
                profile = src.profile.copy()
                profile.update(
                    driver="COG",
                    compress="deflate",
                )
                with rasterio.open(output_cog_path, "w", **profile) as dst:
                    for band_idx in range(1, src.count + 1):
                        dst.write(src.read(band_idx), band_idx)

        size_bytes = os.path.getsize(output_cog_path)
        resolution_m = 30.0  # FABDEM nominal resolution is 1 arc-second (~30 m at equator, RN-25)
        return size_bytes, resolution_m

