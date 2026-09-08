"""Query builder tests (spec §10)."""
from app.services.query_builder import build_search_query


def test_basic_join():
    assert build_search_query("Dentistas", "Córdoba, Argentina") == "Dentistas, Córdoba, Argentina"


def test_does_not_duplicate_location_suffix():
    assert build_search_query("Dentistas en Córdoba", "Córdoba, Argentina") == "Dentistas en Córdoba"


def test_does_not_duplicate_with_comma():
    assert build_search_query("Dentistas, Córdoba", "Córdoba, Argentina") == "Dentistas, Córdoba"


def test_location_embedded_after_marker():
    assert build_search_query("Clínicas estéticas cerca de Pocitos", "Pocitos, Montevideo") == "Clínicas estéticas cerca de Pocitos"


def test_in_marker():
    assert build_search_query("Restaurantes en Palermo", "Palermo, Buenos Aires") == "Restaurantes en Palermo"


def test_no_location():
    assert build_search_query("Dentistas") == "Dentistas"


def test_empty_category_raises():
    import pytest

    with pytest.raises(ValueError):
        build_search_query("   ")
