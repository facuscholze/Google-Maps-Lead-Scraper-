"""Places search facade.

provider resolution:
- "google": live Google Places API (New)
- "mock"  : deterministic offline generator (tests / demo without a key)
- "auto"  : google if an API key is configured, otherwise mock
"""
from __future__ import annotations

from typing import Any, Callable

from app.core.config import settings
from app.core.logging import log_event
from app.integrations.google.client import GooglePlacesClient, NoAPIKeyError, PlacesSearchResult


class GooglePlacesSearch:
    """Small object-like facade; kept for symmetry with providers."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = GooglePlacesClient(api_key)

    async def search(self, query: str, max_results: int) -> PlacesSearchResult:
        return await self._client.search_text(query, max_results)


class MockPlacesSearch:
    """Deterministic synthetic Places results — no network access."""

    def __init__(self, seed: int = 7) -> None:
        self._seed = seed

    async def search(self, query: str, max_results: int) -> PlacesSearchResult:
        from app.integrations.mock_fixtures import generate_places

        places = generate_places(query, max_results, seed=self._seed)
        log_event("mock_places", count=len(places), query=query)
        result = PlacesSearchResult()
        result.places = places
        result.pages_fetched = 1
        result.api_calls = 1
        return result


def resolve_search_provider() -> tuple[str, Callable[..., Any]]:
    mode = getattr(settings, "search_provider", "auto")
    if mode == "mock":
        return "mock", MockPlacesSearch()
    if mode == "google":
        return "google", GooglePlacesSearch()
    # auto
    if settings.google_maps_api_key:
        return "google", GooglePlacesSearch()
    return "mock", MockPlacesSearch()


async def search_places(query: str, max_results: int) -> tuple[str, PlacesSearchResult]:
    """Returns (provider_name, result). Raises PlacesAPIError on live failure."""
    provider_name, provider = resolve_search_provider()
    try:
        result = await provider.search(query, max_results)
    except NoAPIKeyError:
        # In auto mode a missing key should never crash the app: fall back to mock.
        if provider_name == "google":
            log_event("places_no_api_key_fallback_mock")
            return "mock", await MockPlacesSearch().search(query, max_results)
        raise
    return provider_name, result
