"""Mechanical ticker exposure. Filter to the portfolio — never dump the whole book."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from forgecast.schema import ForecastItem, TickerHit
from forgecast.staticdata import ticker_hit, tickers_for


def load_portfolio(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def portfolio_tickers(portfolio: dict[str, Any]) -> set[str]:
    held: set[str] = set()
    for row in portfolio.get("holdings") or []:
        t = row.get("ticker")
        if t:
            held.add(str(t).upper())
    return held


def apply_exposure(item: ForecastItem, portfolio: dict[str, Any]) -> ForecastItem:
    held = portfolio_tickers(portfolio)
    hits: list[TickerHit] = []
    for symbol in tickers_for(item.geo_id):
        if held and symbol not in held:
            continue
        hit = ticker_hit(symbol)
        if hit is None:
            continue
        hits.append(hit)
    item.exposed_tickers = hits
    return item
