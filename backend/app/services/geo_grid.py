"""Grid planning for area sweeps over Google Places Text Search (New).

Official constraints that shape this module (verified 2026-10-14):

- ``searchText`` returns **at most 60 results per query** across all pages.
  https://developers.google.com/maps/documentation/places/web-service/text-search
- ``locationRestriction`` accepts a **rectangle** (low/high lat-lng corners).
  https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText

Strategy: cover the requested area with overlapping rectangular cells, run one
text query per cell, and deduplicate by ``place_id`` (cells overlap on purpose
so edge businesses are not skipped). A cell that hits the 60-result ceiling is
"repleta" (capped): it can optionally be subdivided into 4 child cells.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

# Earth metrics for lat/lng → km conversions.
_KM_PER_DEG_LAT = 110.574
# Minimum edge of a cell we will still subdivide (below this, duplicates cost
# more than the extra coverage is worth).
MIN_CELL_KM = 0.35
# Results per cell that mark it as capped (official hard limit).
CELL_RESULT_CAP = 60


@dataclass(frozen=True)
class GridCell:
    sw_lat: float
    sw_lng: float
    ne_lat: float
    ne_lng: float
    depth: int = 0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.sw_lat + self.ne_lat) / 2, (self.sw_lng + self.ne_lng) / 2)

    def contains(self, lat: float, lng: float) -> bool:
        return self.sw_lat <= lat <= self.ne_lat and self.sw_lng <= lng <= self.ne_lng

    def height_km(self) -> float:
        return abs(self.ne_lat - self.sw_lat) * _KM_PER_DEG_LAT

    def width_km(self) -> float:
        mid_lat = (self.sw_lat + self.ne_lat) / 2
        return abs(self.ne_lng - self.sw_lng) * (111.32 * math.cos(math.radians(mid_lat)))

    def to_restriction(self) -> dict:
        """Payload for the searchText ``locationRestriction.rectangle`` field."""
        return {
            "rectangle": {
                "low": {"latitude": self.sw_lat, "longitude": self.sw_lng},
                "high": {"latitude": self.ne_lat, "longitude": self.ne_lng},
            }
        }


def _km_to_deg_lat(km: float) -> float:
    return km / _KM_PER_DEG_LAT


def _km_to_deg_lng(km: float, at_lat: float) -> float:
    return km / (111.32 * math.cos(math.radians(at_lat)))


def cells_for_bounds(
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    cell_km: float,
    overlap: float = 0.2,
) -> list[GridCell]:
    """Cover a bounding box with overlapping square-ish cells."""
    if cell_km <= 0:
        raise ValueError("cell_km must be positive")
    step_lat = _km_to_deg_lat(cell_km * (1 - overlap))
    lat = sw_lat
    cells: list[GridCell] = []
    while lat < ne_lat:
        cell_ne_lat = min(lat + _km_to_deg_lat(cell_km), ne_lat)
        mid_lat = (lat + cell_ne_lat) / 2
        step_lng = _km_to_deg_lng(cell_km * (1 - overlap), mid_lat)
        cell_lng_span = _km_to_deg_lng(cell_km, mid_lat)
        lng = sw_lng
        while lng < ne_lng:
            cell_ne_lng = min(lng + cell_lng_span, ne_lng)
            cells.append(GridCell(lat, lng, cell_ne_lat, cell_ne_lng))
            lng += step_lng
        lat += step_lat
    return cells


def cells_for_circle(
    center_lat: float,
    center_lng: float,
    radius_m: float,
    cell_km: float,
) -> list[GridCell]:
    """Cells covering a circle (its bounding square, cells kept whole)."""
    radius_km = radius_m / 1000.0
    d_lat = _km_to_deg_lat(radius_km)
    d_lng = _km_to_deg_lng(radius_km, center_lat)
    cells = cells_for_bounds(
        center_lat - d_lat, center_lng - d_lng,
        center_lat + d_lat, center_lng + d_lng,
        cell_km,
    )
    # Keep cells whose center is inside the circle (plus a half-cell margin so
    # the border ring is not lost).
    margin_km = cell_km / 2
    return [
        c for c in cells
        if _haversine_km(center_lat, center_lng, *c.center) <= radius_km + margin_km
    ]


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cells_for_polygon(points: list[tuple[float, float]], cell_km: float) -> list[GridCell]:
    """Cells covering the polygon's bbox whose center falls inside it."""
    if len(points) < 3:
        raise ValueError("a polygon needs at least 3 points")
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    cells = cells_for_bounds(min(lats), min(lngs), max(lats), max(lngs), cell_km)
    return [c for c in cells if _point_in_polygon(c.center, points)]


def _point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting over (lat, lng) pairs — fine for small city polygons."""
    x, y = point[1], point[0]  # work in (lng, lat) plane
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][1], polygon[i][0]
        xj, yj = polygon[j][1], polygon[j][0]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def subdivide(cell: GridCell) -> list[GridCell]:
    """Split a capped cell into 4 overlapping children."""
    mid_lat, mid_lng = cell.center
    pad_lat = (cell.ne_lat - cell.sw_lat) * 0.05
    pad_lng = (cell.ne_lng - cell.sw_lng) * 0.05
    children: list[GridCell] = []
    for s_lat in (cell.sw_lat, mid_lat):
        for s_lng in (cell.sw_lng, mid_lng):
            e_lat = mid_lat if s_lat == cell.sw_lat else cell.ne_lat
            e_lng = mid_lng if s_lng == cell.sw_lng else cell.ne_lng
            children.append(
                GridCell(
                    s_lat - pad_lat if s_lat != cell.sw_lat else s_lat,
                    s_lng - pad_lng if s_lng != cell.sw_lng else s_lng,
                    e_lat + pad_lat if e_lat != cell.ne_lat else e_lat,
                    e_lng + pad_lng if e_lng != cell.ne_lng else e_lng,
                    depth=cell.depth + 1,
                )
            )
    return children


def cells_from_geo(geo: dict, cell_km: float) -> list[GridCell]:
    """Normalize the API geo spec into a cell plan."""
    kind = geo.get("type")
    if kind == "rect":
        sw = geo["sw"]
        ne = geo["ne"]
        return cells_for_bounds(sw[0], sw[1], ne[0], ne[1], cell_km)
    if kind == "circle":
        center = geo["center"]
        return cells_for_circle(center[0], center[1], float(geo["radius_m"]), cell_km)
    if kind == "polygon":
        points = [(float(p[0]), float(p[1])) for p in geo["points"]]
        return cells_for_polygon(points, cell_km)
    raise ValueError(f"unsupported geo type: {kind!r}")


def can_subdivide(cell: GridCell, max_depth: int = 2) -> bool:
    return (
        cell.depth < max_depth
        and cell.width_km() / 2 >= MIN_CELL_KM
        and cell.height_km() / 2 >= MIN_CELL_KM
    )
