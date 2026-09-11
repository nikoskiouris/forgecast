from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import typer

from forgecast.config import (
    DEFAULT_DB,
    DEFAULT_HORIZON_DAYS,
    DEFAULT_PORTFOLIO,
    DEMO_AS_OF,
    HEX_PARQUET,
    MAP_DIR,
    ROOT,
)
from forgecast.explain import headline, render_markdown
from forgecast.graph import Store, dump_timeline
from forgecast.sample import generate_world

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Gridpulse: calibrated map of the AI power buildout.",
)


def _store(db: Path) -> Store:
    return Store(db)


@app.command()
def seed(
    db: Path = typer.Option(DEFAULT_DB, help="SQLite path"),
) -> None:
    """Load the sample world into SQLite."""
    world = generate_world()
    store = _store(db)
    n = store.upsert_events(world.events)
    typer.echo(f"seeded {n} events, {len(world.outcomes)} labeled outcomes → {db}")


@app.command()
def ingest(
    source: str = typer.Option("gdelt", help="gdelt | eia | permits"),
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    db: Path = typer.Option(DEFAULT_DB),
) -> None:
    """Pull optional live feeds (network). Demo does not need this."""
    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    events = []
    src = source.lower()
    if src == "gdelt":
        from forgecast.ingest.gdelt import fetch_gdelt_range

        events = fetch_gdelt_range(s, e)
    elif src == "eia":
        from forgecast.ingest.eia import fetch_eia_load

        events = fetch_eia_load(s, e)
    elif src == "permits":
        from forgecast.ingest.permits import fetch_permits

        events = fetch_permits(s, e)
    else:
        raise typer.BadParameter("source must be gdelt, eia, or permits")
    store = _store(db)
    n = store.upsert_events(events)
    typer.echo(f"ingested {n} {src} events {s} → {e}")


@app.command()
def hexbin(
    res: int = typer.Option(4, help="H3 resolution 3–5"),
    out: Path = typer.Option(HEX_PARQUET),
) -> None:
    """Bake weekly H3 activity parquet from the sample world."""
    from forgecast.hexagg import hex_series, write_hex_parquet

    world = generate_world()
    series = hex_series(world.events, res=res)
    path = write_hex_parquet(series, out)
    typer.echo(f"hexbin {len(series.h3)} cells → {path}")


@app.command()
def bake(
    out: Path = typer.Option(MAP_DIR, help="Folder for map JSON"),
) -> None:
    """Write map / hex / meta JSON under data/map."""
    from forgecast.snapshot import write_json

    write_json(out)
    typer.echo(f"baked JSON → {out}")


@app.command()
def forecast(
    as_of: Optional[str] = typer.Option(None, help="YYYY-MM-DD (default: 2026-06-01)"),
    horizon: int = typer.Option(DEFAULT_HORIZON_DAYS),
    portfolio: Path = typer.Option(DEFAULT_PORTFOLIO),
    db: Path = typer.Option(DEFAULT_DB),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Print calibrated probabilities for the AI power buildout."""
    from forgecast.forecast import forecast as run

    day = date.fromisoformat(as_of) if as_of else DEMO_AS_OF
    store = _store(db) if db.exists() else None
    report = run(as_of=day, horizon_days=horizon, portfolio_path=portfolio, store=store)
    if json_out:
        typer.echo(report.model_dump_json(indent=2))
        return
    skill = f"  |  Brier {report.brier:.2f}  skill {report.brier_skill:+.2f}" if report.brier is not None else ""
    typer.echo(f"Gridpulse  |  as of {report.as_of}  |  horizon {report.horizon_days}d{skill}")
    typer.echo("")
    shown = [i for i in report.items if i.probability >= 0.05][:8] or report.items[:8]
    for item in shown:
        typer.echo(headline(item, report.horizon_days))
        if item.exposed_tickers:
            typer.echo(f"  exposed: {', '.join(t.ticker for t in item.exposed_tickers)}")
        if item.analogs:
            a = item.analogs[0]
            typer.echo(f"  analog: {a.name} ({a.similarity:.0%} similar)")
        typer.echo("")
    typer.echo("Publisher, not an adviser. Use `forgecast report` for the write-up.")


@app.command()
def report(
    as_of: Optional[str] = typer.Option(None),
    rank: int = typer.Option(1, help="1-based rank in the sorted forecast list"),
    portfolio: Path = typer.Option(DEFAULT_PORTFOLIO),
    db: Path = typer.Option(DEFAULT_DB),
) -> None:
    """Full evidence write-up for one forecast."""
    from forgecast.forecast import forecast as run

    day = date.fromisoformat(as_of) if as_of else DEMO_AS_OF
    store = _store(db) if db.exists() else None
    result = run(as_of=day, portfolio_path=portfolio, store=store)
    if not result.items:
        raise typer.Exit(code=1)
    item = result.items[max(0, min(rank, len(result.items)) - 1)]
    typer.echo(render_markdown(item, result.horizon_days))


@app.command()
def backtest(
    start: str = typer.Option("2016-01-01"),
    end: str = typer.Option("2025-07-01"),
) -> None:
    """Walk-forward evaluation. Prints Brier score vs a base-rate baseline."""
    from forgecast.backtest import walk_forward
    from forgecast.staticdata import train_watchlist

    world = generate_world()
    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        train_watchlist(),
        start=date.fromisoformat(start),
        end=date.fromisoformat(end),
    )
    typer.echo(scores.model_dump_json(indent=2))
    if scores.brier_skill > 0:
        typer.echo("ensemble beats the base-rate baseline (positive Brier skill).")
    else:
        typer.echo("ensemble does not beat the base-rate baseline on this window.")


@app.command()
def graph(
    as_of: Optional[str] = typer.Option(None),
    db: Path = typer.Option(DEFAULT_DB),
    limit: int = typer.Option(15),
) -> None:
    """Print recent temporal-graph edges."""
    day = date.fromisoformat(as_of) if as_of else DEMO_AS_OF
    if not db.exists():
        seed(db=db)
    store = _store(db)
    rels = store.recent_relations(day, lookback_days=180)
    for line in dump_timeline(rels, limit=limit):
        typer.echo(line)
    if not rels:
        typer.echo("no relations — run `forgecast seed` first")


@app.command()
def snapshot(
    out: Path = typer.Option(Path("docs"), help="Folder for the static demo site"),
) -> None:
    """Bake the map SPA + JSON. GitHub Pages hosts docs/."""
    from forgecast.snapshot import write_site

    path = write_site(out)
    typer.echo(f"static demo → {out}/  ({path.name})")
    typer.echo("open that folder, or run `forgecast serve`")


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """One process: Gridpulse map + API. Open http://127.0.0.1:8000"""
    import uvicorn

    typer.echo(f"Gridpulse  →  http://{host}:{port}")
    uvicorn.run("forgecast.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
