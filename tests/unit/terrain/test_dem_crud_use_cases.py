"""Unit tests for DEM CRUD use cases (AC-03-07, AC-03-08, AC-03-09, AC-03-11)."""

from uuid import UUID, uuid4

import pytest
from tests.unit.terrain.test_download_dem_job import (
    FakeDemObjectStore,
    InMemoryDemRepository,
)

from agrowave.modules.terrain.application.use_cases.delete_dem import (
    DeleteDem,
    DeleteDemCommand,
)
from agrowave.modules.terrain.application.use_cases.get_dem import GetDem, GetDemQuery
from agrowave.modules.terrain.application.use_cases.list_dems import (
    ListDems,
    ListDemsQuery,
)
from agrowave.modules.terrain.application.use_cases.update_dem import (
    UpdateDem,
    UpdateDemCommand,
)
from agrowave.modules.terrain.domain.errors import (
    DemNotFoundError,
    ResourceInUseError,
)
from agrowave.modules.terrain.domain.models import Bounds, Dem, DemStatus
from agrowave.modules.terrain.domain.ports import DemUsageQuery


class FakeDemUsageQuery(DemUsageQuery):
    """Test double for DemUsageQuery."""

    def __init__(self, in_use_ids: set[UUID] | None = None) -> None:
        self.in_use_ids = in_use_ids or set()

    def is_dem_in_use(self, dem_id: UUID) -> bool:
        return dem_id in self.in_use_ids


def test_ac03_07_list_dems_returns_own_dems() -> None:
    """AC-03-07: Listing DEMs returns only the user's DEMs, supporting search filter."""
    repo = InMemoryDemRepository()
    use_case = ListDems(repo=repo)

    user1 = uuid4()
    user2 = uuid4()

    dem1 = Dem(
        id=uuid4(),
        owner_id=user1,
        name="DEM Boyaca",
        bounds=Bounds(south=5.5, west=-73.4, north=5.6, east=-73.3),
    )
    dem2 = Dem(
        id=uuid4(),
        owner_id=user1,
        name="DEM Santander",
        bounds=Bounds(south=6.5, west=-73.4, north=6.6, east=-73.3),
    )
    dem_foreign = Dem(
        id=uuid4(),
        owner_id=user2,
        name="DEM Boyaca Foreign",
        bounds=Bounds(south=5.5, west=-73.4, north=5.6, east=-73.3),
    )
    repo.save(dem1)
    repo.save(dem2)
    repo.save(dem_foreign)

    # All user1 DEMs
    results = use_case.execute(ListDemsQuery(owner_id=user1))
    assert len(results) == 2
    assert {d.name for d in results} == {"DEM Boyaca", "DEM Santander"}

    # Search filter
    filtered = use_case.execute(ListDemsQuery(owner_id=user1, search="Santander"))
    assert len(filtered) == 1
    assert filtered[0].name == "DEM Santander"


def test_ac03_08_update_dem_metadata() -> None:
    """AC-03-08: Updating DEM changes name and description."""
    repo = InMemoryDemRepository()
    use_case = UpdateDem(repo=repo)

    owner_id = uuid4()
    dem = Dem(
        id=uuid4(),
        owner_id=owner_id,
        name="Old Name",
        description="Old description",
        bounds=Bounds(south=4.6, west=-74.1, north=4.7, east=-74.0),
    )
    repo.save(dem)

    updated = use_case.execute(
        UpdateDemCommand(
            dem_id=dem.id,
            user_id=owner_id,
            name="New Name",
            description="New description",
        )
    )
    assert updated.name == "New Name"
    assert updated.description == "New description"


def test_ac03_11_foreign_dem_returns_not_found() -> None:
    """AC-03-11: Attempting to access or mutate a foreign DEM raises DemNotFoundError."""
    repo = InMemoryDemRepository()
    get_use_case = GetDem(repo=repo)
    update_use_case = UpdateDem(repo=repo)

    owner_id = uuid4()
    other_user = uuid4()
    dem = Dem(
        id=uuid4(),
        owner_id=owner_id,
        name="Private DEM",
        bounds=Bounds(south=4.6, west=-74.1, north=4.7, east=-74.0),
    )
    repo.save(dem)

    with pytest.raises(DemNotFoundError):
        get_use_case.execute(GetDemQuery(dem_id=dem.id, user_id=other_user))

    with pytest.raises(DemNotFoundError):
        update_use_case.execute(
            UpdateDemCommand(
                dem_id=dem.id,
                user_id=other_user,
                name="Hacked",
            )
        )


def test_ac03_09_delete_dem_removes_from_repo_and_store() -> None:
    """AC-03-09: Deleting a DEM removes it from database and object storage."""
    repo = InMemoryDemRepository()
    object_store = FakeDemObjectStore()
    usage_query = FakeDemUsageQuery()

    use_case = DeleteDem(repo=repo, object_store=object_store, usage_query=usage_query)

    owner_id = uuid4()
    dem_id = uuid4()
    key = f"dems/{dem_id}.tif"
    object_store.uploaded_keys.add(key)

    dem = Dem(
        id=dem_id,
        owner_id=owner_id,
        name="DEM to delete",
        bounds=Bounds(south=4.6, west=-74.1, north=4.7, east=-74.0),
        status=DemStatus.AVAILABLE,
        object_key=key,
    )
    repo.save(dem)

    use_case.execute(DeleteDemCommand(dem_id=dem_id, user_id=owner_id))

    assert repo.get_by_id(dem_id) is None
    assert key not in object_store.uploaded_keys


def test_ac03_09_delete_dem_in_use_rejected() -> None:
    """AC-03-09: (RN-28) Deleting a DEM in use by scenarios raises ResourceInUseError."""
    repo = InMemoryDemRepository()
    object_store = FakeDemObjectStore()

    owner_id = uuid4()
    dem_id = uuid4()
    usage_query = FakeDemUsageQuery(in_use_ids={dem_id})

    use_case = DeleteDem(repo=repo, object_store=object_store, usage_query=usage_query)

    dem = Dem(
        id=dem_id,
        owner_id=owner_id,
        name="DEM in use",
        bounds=Bounds(south=4.6, west=-74.1, north=4.7, east=-74.0),
    )
    repo.save(dem)

    with pytest.raises(ResourceInUseError):
        use_case.execute(DeleteDemCommand(dem_id=dem_id, user_id=owner_id))
