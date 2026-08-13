"""Driving geometry between two Atlanta places (public OSRM)."""

from __future__ import annotations

import httpx

from forgecast.ingest.http import get_json

OSRM = "https://router.project-osrm.org/route/v1/driving"


def commute_route(
    http: httpx.Client,
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
) -> list[list[float]]:
    url = f"{OSRM}/{lon1:.5f},{lat1:.5f};{lon2:.5f},{lat2:.5f}"
    data = get_json(
        http,
        url,
        {"overview": "simplified", "geometries": "geojson", "steps": "false"},
    )
    routes = data.get("routes") or [] if isinstance(data, dict) else []
    if not routes:
        return [[lon1, lat1], [lon2, lat2]]
    coords = ((routes[0].get("geometry") or {}).get("coordinates")) or []
    if len(coords) >= 2:
        return coords
    return [[lon1, lat1], [lon2, lat2]]
