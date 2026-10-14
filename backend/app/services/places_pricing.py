"""Google Places API (New) pricing knowledge for cost estimation.

VERIFIED 2026-10-14 against official docs (see docs/AUDIT.md §4):

- Billing is determined by the **highest SKU triggered by any field** in the
  request field mask.
  https://developers.google.com/maps/documentation/places/web-service/usage-and-billing
- Our current field mask requests ``rating``, ``userRatingCount``,
  ``websiteUri``, ``nationalPhoneNumber`` and ``internationalPhoneNumber``,
  which trigger **Text Search Enterprise** (all other fields are ID-Only/Pro).
  https://developers.google.com/maps/documentation/places/web-service/text-search
- Prices change over time: the defaults below mirror the global pricing list
  and can be overridden via environment settings, never hardcoded in callers.
  https://developers.google.com/maps/billing-and-pricing/pricing#places-pricing
"""
from __future__ import annotations

from dataclasses import dataclass

# USD per 1.000 calls, first volume tier (0–100K/month). Source: global pricing
# list, checked 2026-10-14. Free monthly allowance: Pro 5.000 · Enterprise 1.000.
SKU_PRICES_PER_1K_USD = {
    "ESSENTIALS_ID_ONLY": 0.0,
    "PRO": 32.0,
    "ENTERPRISE": 35.0,
    "ENTERPRISE_ATMOSPHERE": 40.0,
}

FREE_CALLS_PER_MONTH = {
    "ESSENTIALS_ID_ONLY": None,  # not billed
    "PRO": 5000,
    "ENTERPRISE": 1000,
    "ENTERPRISE_ATMOSPHERE": 1000,
}

# Fields in our central mask that lift the SKU (see services/field_mask.py).
ENTERPRISE_FIELDS = {
    "places.websiteUri",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.rating",
    "places.userRatingCount",
}

ATMOSPHERE_FIELDS = {"places.reviews"}


@dataclass(frozen=True)
class SkuInfo:
    sku: str
    price_per_1k_usd: float
    free_calls_per_month: int | None
    priced_fields: list[str]


def sku_for_field_mask(mask_fields: list[str], price_per_1k_enterprise: float) -> SkuInfo:
    """Compute the billed SKU for a field mask.

    ``price_per_1k_enterprise`` is the configurable Enterprise price coming from
    settings (so price list updates need no deploy).
    """
    fields = set(mask_fields)
    if fields & ATMOSPHERE_FIELDS:
        sku = "ENTERPRISE_ATMOSPHERE"
    elif fields & ENTERPRISE_FIELDS:
        sku = "ENTERPRISE"
    else:
        sku = "PRO"
    priced = sorted(fields & (ENTERPRISE_FIELDS | ATMOSPHERE_FIELDS))
    price = SKU_PRICES_PER_1K_USD[sku]
    if sku == "ENTERPRISE":
        price = price_per_1k_enterprise
    return SkuInfo(
        sku=sku,
        price_per_1k_usd=price,
        free_calls_per_month=FREE_CALLS_PER_MONTH[sku],
        priced_fields=priced,
    )


def cost_per_call_usd(info: SkuInfo) -> float:
    return info.price_per_1k_usd / 1000.0


def estimate_cost_usd(calls: int, info: SkuInfo) -> float:
    """Estimated billed cost, ignoring the free monthly allowance (we cannot
    know the account's month-to-date usage, so we quote the worst case)."""
    return round(calls * cost_per_call_usd(info), 4)
