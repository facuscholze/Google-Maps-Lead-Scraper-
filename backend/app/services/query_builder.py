"""Intelligent query construction (spec §10).

Avoids duplication such as "Dentistas en Córdoba en Córdoba" when the user
already included a location in the category string, and normalizes tokens.
"""
from __future__ import annotations

import re

# Marker phrases that introduce a location inside the category text.
_MARKERS = ["en", "in", "near", "cerca de", "cerca", "próximo a", "proximo a", "around"]
_MARKER_RE = re.compile(
    r"(?<![a-záéíóúñ0-9])(?:en|in|near|cerca\s+de|cerca|próximo\s+a|proximo\s+a|around)\s+",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"[,\s]+$", "", value)
    return value


def _overlaps(fragment: str, location: str) -> bool:
    """True when `fragment` is already the location (or a prefix of it)."""
    fragment = fragment.strip().strip(",").lower()
    location = location.strip().lower()
    if not fragment or not location:
        return False
    if fragment == location:
        return True
    if location.startswith(fragment + ",") or location.startswith(fragment + " "):
        return True
    return False


def build_search_query(category: str, location: str | None = None) -> str:
    category = _normalize(category)
    location = _normalize(location or "")
    if not category:
        raise ValueError("category is required")
    if not location:
        return category

    # 1) text after a location marker: "Clínicas cerca de Pocitos"
    marker_match = _MARKER_RE.search(category)
    if marker_match:
        fragment = category[marker_match.end():]
        if _overlaps(fragment, location):
            return category
        return f"{category.rstrip(',')}, {location}"

    # 2) trailing segment after a comma: "Dentistas, Córdoba"
    if "," in category:
        last = category.split(",")[-1].strip()
        if _overlaps(last, location):
            return category
        return f"{category.rstrip(',')}, {location}"

    # 3) full location already present inside the text
    if location.lower() in category.lower():
        return category

    return f"{category.rstrip(',')}, {location}"
