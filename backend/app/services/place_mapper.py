"""Maps raw Google Places API results to internal domain values (spec §13).

Pure functions — no DB access. Field names used here are documented by the
Places API (New) and are exactly the ones requested via the field mask.
"""
from __future__ import annotations

from typing import Any

from app.core.enums import WebsiteStatus
from app.models.search import Search


def extract_city_country(formatted_address: str | None) -> tuple[str | None, str | None]:
    if not formatted_address:
        return None, None
    parts = [p.strip() for p in formatted_address.split(",") if p.strip()]
    if not parts:
        return None, None
    country = parts[-1]
    # Heuristic: second-to-last part usually holds the city / administrative area.
    city = parts[-2] if len(parts) >= 2 else None
    return city, country


def map_place(place: dict[str, Any]) -> dict[str, Any]:
    display_name = (place.get("displayName") or {}).get("text") or ""
    location = place.get("location") or {}
    city, country = extract_city_country(place.get("formattedAddress"))
    website = (place.get("websiteUri") or "").strip() or None
    phone = (place.get("nationalPhoneNumber") or "").strip() or None
    international_phone = (place.get("internationalPhoneNumber") or "").strip() or None
    return {
        "place_id": place.get("id") or "",
        "business_name": display_name,
        "primary_type": place.get("primaryType"),
        "category": (place.get("primaryTypeDisplayName") or {}).get("text")
        if isinstance(place.get("primaryTypeDisplayName"), dict)
        else place.get("primaryTypeDisplayName"),
        "address": place.get("formattedAddress"),
        "city": city,
        "country": country,
        "latitude": location.get("latitude") if isinstance(location, dict) else None,
        "longitude": location.get("longitude") if isinstance(location, dict) else None,
        "phone": phone,
        "international_phone": international_phone,
        "website": website,
        "google_maps_url": place.get("googleMapsUri"),
        "rating": place.get("rating"),
        "reviews_count": int(place.get("userRatingCount") or 0),
        "business_status": place.get("businessStatus"),
        "website_status": WebsiteStatus.FOUND.value if website else WebsiteStatus.NONE.value,
        "raw_google_data": place,
    }


def lead_matches_filters(mapped: dict[str, Any], search: Search) -> bool:
    """Apply configured filters (spec §15)."""
    reviews = mapped["reviews_count"]
    if reviews < search.min_reviews:
        return False
    if search.max_reviews is not None and reviews > search.max_reviews:
        return False
    rating = mapped["rating"]
    if rating is None or rating < search.min_rating:
        return False
    if search.only_with_website and not mapped["website"]:
        return False
    if search.only_with_phone and not (mapped["phone"] or mapped["international_phone"]):
        return False
    return True
