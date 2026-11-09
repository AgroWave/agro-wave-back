"""Geodesic domain services for distance and boundary dimensions."""

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agrowave.modules.terrain.domain.models import Bounds, LatLng

# Mean radius of the Earth in kilometers (WGS84 spherical approximation)
EARTH_RADIUS_KM = 6371.0


def geodesic_distance_km(p1: "LatLng", p2: "LatLng") -> float:
    """Calculates great-circle distance between two coordinates in kilometers.

    Applies the spherical Haversine formula on WGS84 coordinates.

    Args:
        p1: Source coordinate with latitude and longitude in decimal degrees.
        p2: Target coordinate with latitude and longitude in decimal degrees.

    Returns:
        Horizontal distance in kilometers.
    """
    lat1_rad = math.radians(p1.lat)
    lat2_rad = math.radians(p2.lat)
    dlat_rad = math.radians(p2.lat - p1.lat)
    dlng_rad = math.radians(p2.lng - p1.lng)

    a = (
        math.sin(dlat_rad / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng_rad / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bounds_dimensions_km(bounds: "Bounds") -> tuple[float, float]:
    """Calculates width and height of a bounding box in kilometers (RN-13).

    Calculates height as the meridional distance between south and north.
    Calculates width as the shortest parallel distance between west and east.

    Args:
        bounds: Axis-aligned geographic bounding box.

    Returns:
        Tuple (width_km, height_km) of bounding box dimensions.
    """
    from agrowave.modules.terrain.domain.models import LatLng

    # Meridional height (constant along lines of longitude)
    height_km = geodesic_distance_km(
        LatLng(lat=bounds.south, lng=bounds.west),
        LatLng(lat=bounds.north, lng=bounds.west),
    )

    # Parallel widths at south and north limits
    width_south_km = geodesic_distance_km(
        LatLng(lat=bounds.south, lng=bounds.west),
        LatLng(lat=bounds.south, lng=bounds.east),
    )
    width_north_km = geodesic_distance_km(
        LatLng(lat=bounds.north, lng=bounds.west),
        LatLng(lat=bounds.north, lng=bounds.east),
    )

    width_km = min(width_south_km, width_north_km)
    return width_km, height_km

