"""Centralized Google Places (New) field mask configuration (spec §11).

Only requested fields are used. Adding a field here adds it to the API call
and — when relevant — to the ingestion mapping.
"""
from __future__ import annotations

PLACES_FIELD_MASK: list[str] = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.googleMapsUri",
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.rating",
    "places.userRatingCount",
    "places.businessStatus",
    "places.primaryType",
    "places.primaryTypeDisplayName",
    "places.types",
    "nextPageToken",
]

# Requested only for the single-place searchText responses that include them.
PLACES_FIELD_MASK_FIELDS = ",".join(PLACES_FIELD_MASK)
