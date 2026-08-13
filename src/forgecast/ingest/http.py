"""Shared HTTP client for live city feeds."""

from __future__ import annotations

import httpx

USER_AGENT = "Forgecast/0.2 (+https://github.com/nikoskiouris/forgecast)"


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=httpx.Timeout(25.0, connect=10.0),
        follow_redirects=True,
    )


def get_json(http: httpx.Client, url: str, params: dict | None = None, headers: dict | None = None) -> dict | list:
    res = http.get(url, params=params, headers=headers)
    res.raise_for_status()
    return res.json()


def post_json(http: httpx.Client, url: str, payload: dict, headers: dict | None = None) -> dict | list:
    res = http.post(url, json=payload, headers=headers)
    res.raise_for_status()
    return res.json()


def arcgis_query(
    http: httpx.Client,
    url: str,
    params: dict,
    page_size: int = 1000,
    max_records: int = 2500,
) -> list[dict]:
    features: list[dict] = []
    offset = 0
    while offset < max_records:
        page = min(page_size, max_records - offset)
        q = {
            **params,
            "f": "json",
            "outSR": 4326,
            "resultOffset": offset,
            "resultRecordCount": page,
        }
        data = get_json(http, url, q)
        if isinstance(data, dict) and data.get("error"):
            raise RuntimeError(str(data["error"]))
        if not isinstance(data, dict):
            break
        chunk = data.get("features") or []
        features.extend(chunk)
        if not chunk or (not data.get("exceededTransferLimit") and len(chunk) < page):
            break
        offset += len(chunk)
    return features
