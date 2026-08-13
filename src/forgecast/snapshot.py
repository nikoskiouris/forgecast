"""Bake JSON + copy the SPA so GitHub Pages can host Gridpulse."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from forgecast import __version__
from forgecast.config import DEFAULT_HORIZON_DAYS, DEMO_AS_OF, ROOT, WEB_DIST
from forgecast.forecast import forecast
from forgecast.geo import build_map
from forgecast.hexagg import hex_series, week_index
from forgecast.sample import generate_world
from forgecast.staticdata import train_watchlist


def write_json(out: Path, as_of: date | None = None) -> dict:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    as_of = as_of or DEMO_AS_OF
    world = generate_world()
    report = forecast(as_of=as_of, top_n=16)
    payload = build_map(report, events=world.events)
    known = [e for e in world.events if e.timestamp.date() <= as_of]
    series = hex_series(known, res=4)

    from forgecast.backtest import walk_forward

    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        train_watchlist(),
        start=date(2016, 1, 1),
        end=date(2025, 7, 1),
    )
    report.brier = scores.brier
    report.brier_skill = scores.brier_skill
    meta = {
        "product": "Gridpulse",
        "version": __version__,
        "as_of": as_of.isoformat(),
        "horizon_days": DEFAULT_HORIZON_DAYS,
        "week": week_index(as_of),
        "n": scores.n,
        "brier": scores.brier,
        "brier_skill": scores.brier_skill,
        "base_rate": scores.base_rate,
        "disclaimer": "Publisher, not an adviser. Mechanical ticker exposure is not a recommendation.",
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    (out / "forecast.json").write_text(report.model_dump_json(indent=2))
    (out / "map.json").write_text(payload.model_dump_json(indent=2))
    (out / "hex.json").write_text(series.model_dump_json(indent=2))
    return meta


def write_site(out: Path) -> Path:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dist = WEB_DIST if WEB_DIST.is_dir() else None
    if dist and (dist / "index.html").is_file():
        for child in dist.iterdir():
            dest = out / child.name
            if dest.exists() and dest.is_dir():
                shutil.rmtree(dest)
            elif dest.exists():
                dest.unlink()
            if child.is_dir():
                shutil.copytree(child, dest)
            else:
                shutil.copy2(child, dest)
    (out / ".nojekyll").write_text("")
    data_dir = out / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    write_json(data_dir)
    return data_dir / "map.json"


def default_docs_dir() -> Path:
    return ROOT / "docs"
