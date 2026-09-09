"""Mock Places provider determinism, pagination shape and dedupe ids."""
from app.integrations.mock_fixtures import generate_places, get_profile_for_slug


def test_generates_requested_count():
    assert len(generate_places("test", 100, seed=7)) == 100


def test_deterministic_same_seed():
    a = generate_places("x", 50, seed=3)
    b = generate_places("x", 50, seed=3)
    assert a == b


def test_unique_place_ids():
    places = generate_places("x", 100, seed=0)
    ids = [p["id"] for p in places]
    assert len(ids) == len(set(ids))


def test_profile_variant_slug_resolves():
    p = generate_places("x", 100, seed=7)[60]
    slug = p["_mock"]["slug"]
    assert get_profile_for_slug(slug) is not None


def test_places_have_required_google_fields():
    place = generate_places("clínicas", 1, seed=1)[0]
    for field in ("id", "displayName", "formattedAddress", "location", "rating", "userRatingCount"):
        assert field in place
