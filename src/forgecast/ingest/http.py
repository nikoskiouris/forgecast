"""Shared HTTP helper for optional live feeds."""

from __future__ import annotations

import httpx

USER_AGENT = "Gridpulse/0.3 (+https://github.com/nikoskiouris/forgecast)"


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=httpx.Timeout(25.0, connect=10.0),
        follow_redirects=True,
    )
