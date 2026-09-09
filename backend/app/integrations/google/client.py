"""Google Places API (New) — text search client (spec §6, §12).

Implements https://places.googleapis.com/v1/places:searchText with proper
pagination (nextPageToken), retries, field masks, and request logging.
It never touches Google Maps HTML scraping or browser automation.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import log_event
from app.services.field_mask import PLACES_FIELD_MASK_FIELDS

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"


class PlacesAPIError(Exception):
    """Raised on unrecoverable Google Places API errors."""


class NoAPIKeyError(PlacesAPIError):
    def __init__(self) -> None:
        super().__init__(
            "GOOGLE_MAPS_API_KEY is not configured. Add it to the backend environment."
        )


def _retryable(exc: Exception) -> bool:
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError, PlacesAPIError))


@dataclass
class PlacesPage:
    places: list[dict[str, Any]]
    next_page_token: str | None = None
    page_index: int = 0
    api_calls: int = 1


@dataclass
class PlacesSearchResult:
    places: list[dict[str, Any]] = field(default_factory=list)
    next_page_token: str | None = None
    pages_fetched: int = 0
    api_calls: int = 0
    truncated: bool = False


class GooglePlacesClient:
    """Async client for the Places (New) text-search endpoint."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key or settings.google_maps_api_key).strip()
        if not self._api_key:
            raise NoAPIKeyError()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": PLACES_FIELD_MASK_FIELDS,
        }

    @retry(
        retry=retry_if_exception(_retryable),
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def _post(self, client: httpx.AsyncClient, body: dict[str, Any]) -> dict[str, Any]:
        log_event("google_request", url=PLACES_TEXT_SEARCH_URL, fields=PLACES_FIELD_MASK_FIELDS)
        response = await client.post(PLACES_TEXT_SEARCH_URL, json=body)
        if response.status_code == 200:
            log_event("google_response", status_code=200)
            return response.json()
        # 4xx other than rate limiting are not retryable.
        if response.status_code in (400, 401, 403):
            try:
                error = response.json().get("error", {}).get("message", "")
            except Exception:
                error = ""
            raise PlacesAPIError(
                f"Google Places API error {response.status_code}: {error or response.text[:300]}"
            )
        log_event("google_response", status_code=response.status_code)
        response.raise_for_status()
        return response.json()

    async def search_text(
        self,
        query: str,
        max_results: int,
        page_size: int = 20,
        language: str = "es",
        region_code: str | None = None,
    ) -> PlacesSearchResult:
        if not query.strip():
            raise ValueError("query is required")
        max_results = min(max(max_results, 1), settings.max_results_per_search)
        result = PlacesSearchResult()
        token: str | None = None
        api_calls = 0
        timeout = httpx.Timeout(settings.google_request_timeout)

        async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
            while True:
                body: dict[str, Any] = {
                    "textQuery": query,
                    "pageSize": min(page_size, 20),
                    "languageCode": language,
                }
                if region_code:
                    body["regionCode"] = region_code
                if token:
                    body["pageToken"] = token

                data = await self._post(client, body)
                api_calls += 1
                places = data.get("places") or []
                result.places.extend(places)
                result.api_calls = api_calls
                token = data.get("nextPageToken")
                result.pages_fetched += 1

                if token is None:
                    break
                if len(result.places) >= max_results:
                    result.truncated = True
                    break
                if result.pages_fetched >= 20:  # safety valve — never loop forever
                    result.truncated = True
                    break
        return result


async def fetch_places_async(
    query: str, max_results: int, api_key: str | None = None
) -> PlacesSearchResult:
    client = GooglePlacesClient(api_key)
    return await client.search_text(query, max_results)


def fetch_places(
    query: str, max_results: int, api_key: str | None = None
) -> PlacesSearchResult:
    """Synchronous convenience wrapper (useful for workers/tests)."""
    return asyncio.run(fetch_places_async(query, max_results, api_key))