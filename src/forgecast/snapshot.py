"""Bake a static demo so GitHub Pages can host the map with no backend."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from forgecast.config import DEFAULT_HORIZON_DAYS, DEFAULT_PORTFOLIO, DEMO_AS_OF, ROOT
from forgecast.exposure import load_portfolio
from forgecast.forecast import WATCHLIST, forecast, load_training_world
from forgecast.geo import build_map
from forgecast.schema import DemoBundle, MapPayload

WEB = Path(__file__).parent / "web"
DEMO_DATES = (date(2023, 6, 1), date(2024, 1, 1), date(2024, 6, 1))


def snapshot_for(as_of: date, horizon_days: int = DEFAULT_HORIZON_DAYS) -> MapPayload:
    events, _outcomes = load_training_world()
    report = forecast(as_of=as_of, horizon_days=horizon_days, top_n=len(WATCHLIST))
    portfolio = load_portfolio(DEFAULT_PORTFOLIO) if DEFAULT_PORTFOLIO.exists() else {}
    return build_map(report, portfolio=portfolio, events=events)


def build_bundle(
    dates: tuple[date, ...] | list[date] = DEMO_DATES,
    default_as_of: date = DEMO_AS_OF,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
) -> DemoBundle:
    ordered = sorted(set(dates))
    snapshots = {d.isoformat(): snapshot_for(d, horizon_days) for d in ordered}
    if default_as_of.isoformat() not in snapshots:
        snapshots[default_as_of.isoformat()] = snapshot_for(default_as_of, horizon_days)
        ordered = sorted(date.fromisoformat(k) for k in snapshots)
    return DemoBundle(
        default_as_of=default_as_of,
        horizon_days=horizon_days,
        dates=ordered,
        snapshots=snapshots,
    )


def write_site(out: Path, bundle: DemoBundle | None = None) -> Path:
    """Copy the map UI and write data/demo.json into `out` (usually docs/)."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    assets_src = WEB / "assets"
    if assets_src.exists():
        dest = out / "assets"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(assets_src, dest)
    index = WEB / "index.html"
    if index.exists():
        shutil.copy(index, out / "index.html")
    (out / ".nojekyll").write_text("")
    data_dir = out / "data"
    data_dir.mkdir(exist_ok=True)
    payload = bundle or build_bundle()
    (data_dir / "demo.json").write_text(payload.model_dump_json(indent=2))
    return out / "data" / "demo.json"


def default_docs_dir() -> Path:
    return ROOT / "docs"
