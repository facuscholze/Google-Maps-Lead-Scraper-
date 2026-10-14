"""Secondary lead dedup signals (chains & branches share place_ids never, but
they often share a phone number or a website domain).

Primary dedupe is always ``(workspace_id, place_id)`` — enforced by a DB unique
constraint. These helpers give a *second* chance to recognize the same business
when Google returns distinct records for it (e.g. two listings, one per floor).
"""
from __future__ import annotations

import re
import urllib.parse


def normalize_phone(value: str | None) -> str | None:
    """Digits only, local 0 access codes stripped. None when not a phone."""
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) < 8:
        return None
    # Canonical: country code kept when present; leading trunk zeros stripped.
    return digits.lstrip("0") or None


# Hosts where the PATH, not the host, identifies the business (social pages,
# directories, booking platforms, and our own offline fixture server).
# Using these as a dedupe key would merge every business under one platform.
PLATFORM_HOSTS = {
    "facebook.com", "instagram.com", "wa.me", "whatsapp.com", "linktr.ee",
    "maps.google.com", "google.com", "g.page", "yelp.com", "tripadvisor.com",
    "booking.com", "pedidosya.com", "mercadopago.com", "t.me",
    "mockbusiness.local",  # offline fixtures: /{slug} is the identity
}


def normalize_domain(website: str | None) -> str | None:
    """Host of a website URL (lowercase, no www) — or None when the host is a
    shared platform where the path (not the domain) identifies the business."""
    if not website:
        return None
    host = urllib.parse.urlparse(website if "://" in website else f"http://{website}").netloc
    host = host.lower().strip()
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    if host in PLATFORM_HOSTS:
        return None
    return host or None
