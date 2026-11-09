"""Unit tests for terrain domain models, rules, and calculations (AC-03-02, AC-03-03, AC-03-04)."""

import pytest

from agrowave.modules.terrain.domain.errors import (
    AreaTooSmallError,
    InvalidBoundsError,
)
from agrowave.modules.terrain.domain.models import Bounds, LatLng, StudyArea
from agrowave.modules.terrain.domain.services import (
    bounds_dimensions_km,
    geodesic_distance_km,
)
from agrowave.modules.terrain.infrastructure.colombia_territory_boundary import (
    ColombiaTerritoryBoundary,
)


def test_ac03_04_invalid_bounds_rejected() -> None:
    """Verifies that Bounds with south >= north or west >= east raise InvalidBoundsError."""
    # south >= north
    with pytest.raises(InvalidBoundsError):
        Bounds(south=5.0, west=-74.0, north=4.0, east=-73.0)

    # west >= east
    with pytest.raises(InvalidBoundsError):
        Bounds(south=4.0, west=-73.0, north=5.0, east=-74.0)

    # Valid bounds
    b = Bounds(south=4.0, west=-74.0, north=5.0, east=-73.0)
    assert b.south == 4.0
    assert b.west == -74.0
    assert b.north == 5.0
    assert b.east == -73.0


def test_ac03_03_area_too_small_rejected() -> None:
    """AC-03-03: (RN-13) Study area smaller than 1.5 km per side raises AreaTooSmallError."""
    # A tiny bounding box (~100 meters)
    tiny_bounds = Bounds(south=4.000, west=-74.000, north=4.001, east=-73.999)
    width_km, height_km = bounds_dimensions_km(tiny_bounds)
    assert width_km < 1.5
    assert height_km < 1.5

    with pytest.raises(AreaTooSmallError):
        StudyArea(bounds=tiny_bounds)

    # Valid 2 km x 2 km box near Bogota (~0.018 deg lat, ~0.018 deg lng)
    valid_bounds = Bounds(south=4.60, west=-74.10, north=4.62, east=-74.08)
    w, h = bounds_dimensions_km(valid_bounds)
    assert w >= 1.5
    assert h >= 1.5

    study_area = StudyArea(bounds=valid_bounds)
    assert study_area.bounds == valid_bounds


def test_ac03_02_area_outside_colombia_rejected() -> None:
    """AC-03-02: (RN-12) Bounding box outside continental Colombia is rejected."""
    boundary = ColombiaTerritoryBoundary()

    # In continental Colombia (Boyaca altiplano)
    boyaca_bounds = Bounds(south=5.5, west=-73.4, north=5.6, east=-73.3)
    assert boundary.is_within_colombia_continental(boyaca_bounds) is True

    # In oceanic islands: San Andres (lon ~-81.7, lat ~12.58)
    san_andres_bounds = Bounds(south=12.50, west=-81.75, north=12.60, east=-81.65)
    assert boundary.is_within_colombia_continental(san_andres_bounds) is False

    # Outside Colombia: Paris, France
    france_bounds = Bounds(south=48.8, west=2.3, north=48.9, east=2.4)
    assert boundary.is_within_colombia_continental(france_bounds) is False


def test_geodesic_distance_calculation() -> None:
    """Verifies horizontal distance between two points using pure geodesic formula."""
    p1 = LatLng(lat=4.6097, lng=-74.0817)
    p2 = LatLng(lat=4.6197, lng=-74.0817)
    dist = geodesic_distance_km(p1, p2)
    # 0.01 deg latitude is approx 1.11 km
    assert 1.0 < dist < 1.2
