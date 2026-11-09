"""Continental Colombia territory boundary adapter (RN-12)."""

from shapely.geometry import Polygon, box

from agrowave.modules.terrain.domain.models import Bounds
from agrowave.modules.terrain.domain.ports import TerritoryBoundary

# Simplified polygon of continental Colombia (excluding oceanic islands).
# Coordinates given in (lon, lat) WGS84.
_COLOMBIA_CONTINENTAL_COORDS = [
    (-71.66, 12.46),  # Punta Gallinas (Guajira)
    (-71.10, 11.85),
    (-71.75, 10.90),
    (-72.35, 9.40),
    (-72.45, 8.00),
    (-70.40, 7.05),
    (-67.40, 6.20),  # Puerto Carreño
    (-67.80, 3.85),  # Inírida
    (-66.85, 1.23),  # Isla San José (Guainía / Río Negro)
    (-69.45, 0.05),
    (-69.80, -1.20),
    (-69.95, -4.23),  # Leticia
    (-70.50, -4.25),
    (-74.00, -2.00),
    (-75.20, -0.50),
    (-77.50, 0.80),
    (-78.80, 1.50),
    (-79.03, 1.65),  # Cabo Manglares
    (-77.50, 4.00),  # Buenaventura
    (-77.60, 7.00),
    (-77.90, 7.20),  # Border with Panama
    (-77.30, 8.60),  # Urabá
    (-75.80, 9.50),
    (-75.50, 10.50),  # Cartagena
    (-74.80, 11.00),  # Barranquilla
    (-74.20, 11.25),  # Santa Marta
    (-72.50, 11.75),  # Riohacha
    (-71.66, 12.46),
]


class ColombiaTerritoryBoundary(TerritoryBoundary):
    """Adapter verifying if bounds fall entirely within continental Colombia (RN-12)."""

    def __init__(self, buffer_degrees: float = 0.05) -> None:
        """Initializes the territory boundary polygon with a slight boundary tolerance.

        Args:
            buffer_degrees: Geometric buffer in degrees to account for coastal/border margins.
        """
        raw_poly = Polygon(_COLOMBIA_CONTINENTAL_COORDS)
        self._poly = raw_poly.buffer(buffer_degrees)
        # Strict continental envelope bounds
        self._min_lon = -79.15
        self._max_lon = -66.80
        self._min_lat = -4.30
        self._max_lat = 12.55

    def is_within_colombia_continental(self, bounds: Bounds) -> bool:
        """Checks if the bounding box is within continental Colombia.

        Args:
            bounds: Bounding box to check.

        Returns:
            True if bounds are strictly within continental Colombia boundaries.
        """
        if (
            bounds.west < self._min_lon
            or bounds.east > self._max_lon
            or bounds.south < self._min_lat
            or bounds.north > self._max_lat
        ):
            return False

        b_box = box(bounds.west, bounds.south, bounds.east, bounds.north)
        return bool(self._poly.intersects(b_box) and self._poly.contains(b_box.centroid))
