"""Mapping + filter logic tests (spec §14-15)."""
from app.integrations.mock_fixtures import generate_places
from app.models.search import Search
from app.services.place_mapper import lead_matches_filters, map_place


def _search(**overrides) -> Search:
    defaults = dict(
        workspace_id=1,
        query="x",
        min_reviews=0,
        max_reviews=None,
        min_rating=0.0,
        only_with_website=False,
        only_with_phone=False,
    )
    defaults.update(overrides)
    search = Search(**defaults)
    return search


def test_map_place_fields():
    raw = generate_places("clínicas estéticas", 1, seed=4)[0]
    mapped = map_place(raw)
    assert mapped["place_id"]
    assert mapped["business_name"]
    assert mapped["country"] == "Uruguay"
    assert mapped["website_status"] in ("FOUND", "NONE")
    assert "latitude" in mapped and "longitude" in mapped


def test_review_range_filter():
    for place in generate_places("x", 100, seed=0):
        mapped = map_place(place)
        search = _search(min_reviews=50, max_reviews=500, min_rating=4.0)
        matches = lead_matches_filters(mapped, search)
        if matches:
            assert 50 <= mapped["reviews_count"] <= 500
            assert mapped["rating"] >= 4.0


def test_website_only_filter():
    for place in generate_places("x", 60, seed=1):
        mapped = map_place(place)
        search = _search(only_with_website=True)
        assert lead_matches_filters(mapped, search) == bool(mapped["website"])


def test_phone_only_filter():
    for place in generate_places("x", 60, seed=1):
        mapped = map_place(place)
        search = _search(only_with_phone=True)
        assert lead_matches_filters(mapped, search) == bool(mapped["phone"] or mapped["international_phone"])
