"""Unit tests for DEM download use cases and background processing (AC-03-05, AC-03-06)."""

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from agrowave.modules.terrain.application.use_cases.process_dem_download import (
    ProcessDemDownload,
    ProcessDemDownloadCommand,
)
from agrowave.modules.terrain.application.use_cases.request_dem_download import (
    RequestDemDownload,
    RequestDemDownloadCommand,
)
from agrowave.modules.terrain.domain.errors import (
    AreaOutsideColombiaError,
)
from agrowave.modules.terrain.domain.models import Bounds, Dem, DemStatus
from agrowave.modules.terrain.domain.ports import (
    DemObjectStore,
    DemRepository,
    ElevationSource,
    TerritoryBoundary,
)


class InMemoryDemRepository(DemRepository):
    """In-memory test double for DemRepository."""

    def __init__(self) -> None:
        self.dems: dict[UUID, Dem] = {}

    def save(self, dem: Dem) -> None:
        self.dems[dem.id] = dem

    def get_by_id(self, dem_id: UUID) -> Dem | None:
        return self.dems.get(dem_id)

    def list_by_owner(self, owner_id: UUID, search: str | None = None) -> list[Dem]:
        results = [d for d in self.dems.values() if d.owner_id == owner_id]
        if search:
            q = search.lower()
            results = [d for d in results if q in d.name.lower()]
        return sorted(results, key=lambda d: d.created_at, reverse=True)

    def delete(self, dem_id: UUID) -> None:
        self.dems.pop(dem_id, None)


class InMemoryTerritoryBoundary(TerritoryBoundary):
    """Test double for continental Colombia territory boundary."""

    def __init__(self, is_in_colombia: bool = True) -> None:
        self.is_in_colombia = is_in_colombia

    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        return self.is_in_colombia


class FakeElevationSource(ElevationSource):
    """Test double for ElevationSource that simulates raster download."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.downloaded_bounds: Bounds | None = None

    def download_and_mosaic(self, bounds: Bounds, output_cog_path: Path) -> tuple[int, float]:
        if self.should_fail:
            raise RuntimeError("FABDEM tile download error: network unreachable")
        self.downloaded_bounds = bounds
        output_cog_path.touch()
        return 1024 * 1024, 30.0


class FakeDemObjectStore(DemObjectStore):
    """Test double for DemObjectStore."""

    def __init__(self) -> None:
        self.uploaded_keys: set[str] = set()

    def upload_file(self, key: str, file_path: Path) -> None:
        self.uploaded_keys.add(key)

    def delete_file(self, key: str) -> None:
        self.uploaded_keys.discard(key)


def test_ac03_01_request_dem_download_creates_downloading_dem() -> None:
    """AC-03-01: Valid request creates a Dem in DOWNLOADING status."""
    repo = InMemoryDemRepository()
    territory = InMemoryTerritoryBoundary(is_in_colombia=True)
    use_case = RequestDemDownload(repo=repo, territory_boundary=territory)

    user_id = uuid4()
    bounds = Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08)

    dem = use_case.execute(
        RequestDemDownloadCommand(
            owner_id=user_id,
            name="Valle de Sopó",
            bounds=bounds,
            description="Zona rural Cundinamarca",
        )
    )

    assert dem.status == DemStatus.DOWNLOADING
    assert dem.owner_id == user_id
    assert dem.name == "Valle de Sopó"
    assert dem.description == "Zona rural Cundinamarca"
    assert repo.get_by_id(dem.id) is not None


def test_ac03_02_area_outside_colombia_rejected() -> None:
    """AC-03-02: (RN-12) Bounding box outside Colombia raises AreaOutsideColombiaError."""
    repo = InMemoryDemRepository()
    territory = InMemoryTerritoryBoundary(is_in_colombia=False)
    use_case = RequestDemDownload(repo=repo, territory_boundary=territory)

    bounds = Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08)
    with pytest.raises(AreaOutsideColombiaError):
        use_case.execute(
            RequestDemDownloadCommand(
                owner_id=uuid4(),
                name="Outside Colombia",
                bounds=bounds,
            )
        )


def test_ac03_05_dem_job_success_sets_available(tmp_path: Path) -> None:
    """AC-03-05: Successful download job updates status to AVAILABLE with size and resolution."""
    repo = InMemoryDemRepository()
    elevation_source = FakeElevationSource(should_fail=False)
    object_store = FakeDemObjectStore()

    dem = Dem(
        id=uuid4(),
        owner_id=uuid4(),
        name="Test DEM",
        bounds=Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08),
        status=DemStatus.DOWNLOADING,
    )
    repo.save(dem)

    job = ProcessDemDownload(
        repo=repo,
        elevation_source=elevation_source,
        object_store=object_store,
        temp_dir=tmp_path,
    )
    job.execute(ProcessDemDownloadCommand(dem_id=dem.id))

    updated_dem = repo.get_by_id(dem.id)
    assert updated_dem is not None
    assert updated_dem.status == DemStatus.AVAILABLE
    assert updated_dem.object_key == f"dems/{dem.id}.tif"
    assert updated_dem.size_bytes == 1024 * 1024
    assert updated_dem.resolution_m == 30.0
    assert updated_dem.failure_reason is None
    assert f"dems/{dem.id}.tif" in object_store.uploaded_keys


def test_ac03_06_dem_job_failure_sets_failed(tmp_path: Path) -> None:
    """AC-03-06: Failed download job sets status to FAILED with error message."""
    repo = InMemoryDemRepository()
    elevation_source = FakeElevationSource(should_fail=True)
    object_store = FakeDemObjectStore()

    dem = Dem(
        id=uuid4(),
        owner_id=uuid4(),
        name="Failing DEM",
        bounds=Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08),
        status=DemStatus.DOWNLOADING,
    )
    repo.save(dem)

    job = ProcessDemDownload(
        repo=repo,
        elevation_source=elevation_source,
        object_store=object_store,
        temp_dir=tmp_path,
    )
    job.execute(ProcessDemDownloadCommand(dem_id=dem.id))

    updated_dem = repo.get_by_id(dem.id)
    assert updated_dem is not None
    assert updated_dem.status == DemStatus.FAILED
    assert updated_dem.object_key is None
    assert "network unreachable" in (updated_dem.failure_reason or "")
