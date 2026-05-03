"""Nominatim geocoding wrapper with simple in-process cache."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "gf2map/0.1 (personal use)"

_cache: dict[str, Tuple[float, float]] = {}


class GeocodeError(Exception):
    """Raised when an address cannot be geocoded."""


def geocode(address: str, *, client: Optional[httpx.Client] = None) -> Tuple[float, float]:
    """Resolve free-form address text to (lat, lng) using Nominatim.

    Results are cached in-process by normalized address string.
    Raises GeocodeError if no result is found.
    """
    key = address.strip().lower()
    if not key:
        raise GeocodeError("Address is empty.")

    if key in _cache:
        logger.info("Geocode cache hit for %r", key)
        return _cache[key]

    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=15.0)

    try:
        resp = client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise GeocodeError(f"Geocoding service error: {e}") from e
    finally:
        if owns_client:
            client.close()

    if not data:
        raise GeocodeError(f"Address not found: {address!r}")

    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
    except (KeyError, ValueError, TypeError) as e:
        raise GeocodeError(f"Unexpected geocoding response: {e}") from e

    _cache[key] = (lat, lon)
    logger.info("Geocoded %r -> (%s, %s)", address, lat, lon)
    return lat, lon
