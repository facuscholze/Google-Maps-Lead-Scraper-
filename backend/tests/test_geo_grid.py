"""Grid-sweep maths: coverage, cell structure, subdivision (Fase 2)."""
from __future__ import annotations

import pytest

from app.services import geo_grid


# ~4km x ~3km area over Montevideo
SW = (-34.94, -56.20)
NE = (-34.90, -56.15)


def test_cells_cover_bounds_with_overlap():
    cells = geo_grid.cells_for_bounds(SW[0], SW[1], NE[0], NE[1], cell_km=1.5)
    assert cells, "expected a non-empty plan"
    assert len(set(cells)) == len(cells), "cells must be unique"
    for cell in cells:
        # every cell starts inside (or at) the requested bounds
        assert SW[0] - 1e-9 <= cell.sw_lat < NE[0]
        assert SW[1] - 1e-9 <= cell.sw_lng < NE[1]
        # and extends up to/into the bounds (never fully outside)
        assert cell.ne_lat > SW[0]
        assert cell.ne_lng > SW[1]


def test_bigger_area_more_cells_smaller_cell_fewer():
    fine = geo_grid.cells_for_bounds(SW[0], SW[1], NE[0], NE[1], 1.0)
    coarse = geo_grid.cells_for_bounds(SW[0], SW[1], NE[0], NE[1], cell_km=3.0)
    assert len(fine) > len(coarse) > 0


def test_to_restriction_matches_places_api_shape():
    cell = geo_grid.cells_for_bounds(SW[0], SW[1], SW[0] + 0.01, SW[1] + 0.01, 1.5)[0]
    restriction = cell.to_restriction()
    rect = restriction["rectangle"]
    assert rect["low"]["latitude"] == pytest.approx(cell.sw_lat)
    assert rect["high"]["latitude"] == pytest.approx(cell.ne_lat)
    assert rect["low"]["longitude"] == pytest.approx(cell.sw_lng)
    assert rect["high"]["longitude"] == pytest.approx(cell.ne_lng)


def test_circle_plan_covers_center():
    center = (-34.9033, -56.1882)
    cells = geo_grid.cells_from_geo(
        {"type": "circle", "center": list(center), "radius_m": 1500.0}, cell_km=1.0
    )
    assert cells
    hits = [c for c in cells if c.contains(center[0], center[1])]
    assert hits, "center of the circle must lie in at least one cell"


def test_polygon_plan_covers_triangle_interior():
    pts = [[-34.94, -56.20], [-34.90, -56.20], [-34.92, -56.15]]
    cells = geo_grid.cells_from_geo({"type": "polygon", "points": pts}, cell_km=0.8)
    assert cells
    centroid = (
        sum(p[0] for p in pts) / 3,
        sum(p[1] for p in pts) / 3,
    )
    assert any(c.contains(*centroid) for c in cells)


def test_subdivide_quarters_and_depth_guard():
    cell = geo_grid.cells_for_bounds(SW[0], SW[1], SW[0] + 0.02, SW[1] + 0.02, 1.5)[0]
    children = geo_grid.subdivide(cell)
    assert len(children) == 4
    assert all(c.depth == cell.depth + 1 for c in children)
    # union of children covers the parent (with overlap)
    sample = ((cell.sw_lat + cell.ne_lat) / 2, (cell.sw_lng + cell.ne_lng) / 2)
    assert sum(c.contains(*sample) for c in children) >= 1
    tiny = geo_grid.GridCell(sw_lat=-34.9, sw_lng=-56.2, ne_lat=-34.9 + 0.004, ne_lng=-56.2 + 0.004, depth=2)
    assert not geo_grid.can_subdivide(tiny, max_depth=2), "max depth reached"
    shallow = geo_grid.GridCell(sw_lat=-34.9, sw_lng=-56.2, ne_lat=-34.899, ne_lng=-56.199, depth=0)
    assert not geo_grid.can_subdivide(shallow, max_depth=2), "children below MIN_CELL_KM"


def test_cells_from_geo_rejects_unknown():
    with pytest.raises(ValueError):
        geo_grid.cells_from_geo({"type": "spiral"}, 1.5)
