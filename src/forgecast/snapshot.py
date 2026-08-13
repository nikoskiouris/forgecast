"""Bake a static Atlanta snapshot so GitHub Pages can host the map."""

from __future__ import annotations

import shutil
from pathlib import Path

from forgecast.config import ROOT
from forgecast.ingest.live import fetch_city_events
from forgecast.schema import CityBundle

WEB = Path(__file__).parent / "web"


def write_site(out: Path, bundle: CityBundle | None = None) -> Path:
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
    payload = bundle or fetch_city_events()
    target = data_dir / "demo.json"
    target.write_text(payload.model_dump_json(indent=2))
    return target


def default_docs_dir() -> Path:
    return ROOT / "docs"
