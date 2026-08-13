from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import typer

from forgecast.config import DEFAULT_DB, DEFAULT_HORIZON_DAYS, DEFAULT_PORTFOLIO, DEMO_AS_OF
from forgecast.explain import headline, render_markdown
from forgecast.graph import Store, dump_timeline
from forgecast.sample import generate_world

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Atlanta day briefing: what will affect your places, routes, and routine.",
)


def _store(db: Path) -> Store:
    return Store(db)


@app.command()
def seed(
    db: Path = typer.Option(DEFAULT_DB, help="SQLite path"),
) -> None:
    """Load the historically-inspired sample world into SQLite."""
    world = generate_world()
    store = _store(db)
    n = store.upsert_events(world.events)
    typer.echo(f"seeded {n} events, {len(world.outcomes)} labeled outcomes → {db}")


@app.command()
def ingest(
    start: str = typer.Option(..., help="YYYY-MM-DD"),
    end: str = typer.Option(..., help="YYYY-MM-DD"),
    db: Path = typer.Option(DEFAULT_DB),
) -> None:
    """Pull GDELT daily events into the store (network)."""
    from forgecast.ingest.gdelt import fetch_gdelt_range

    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    events = fetch_gdelt_range(s, e)
    store = _store(db)
    n = store.upsert_events(events)
    typer.echo(f"ingested {n} GDELT events {s} → {e}")


@app.command()
def forecast(
    as_of: Optional[str] = typer.Option(None, help="YYYY-MM-DD (default: 2024-06-01 demo date)"),
    horizon: int = typer.Option(DEFAULT_HORIZON_DAYS),
    portfolio: Path = typer.Option(DEFAULT_PORTFOLIO),
    db: Path = typer.Option(DEFAULT_DB),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Print calibrated disruption probabilities for the demo portfolio."""
    from forgecast.forecast import forecast as run

    day = date.fromisoformat(as_of) if as_of else DEMO_AS_OF
    store = _store(db) if db.exists() else None
    report = run(as_of=day, horizon_days=horizon, portfolio_path=portfolio, store=store)
    if json_out:
        typer.echo(report.model_dump_json(indent=2))
        return
    typer.echo(f"Forgecast  |  as of {report.as_of}  |  horizon {report.horizon_days}d  |  {report.portfolio}")
    typer.echo("")
    for item in report.items:
        typer.echo(headline(item, report.horizon_days))
        if item.exposed_programs:
            typer.echo(
                f"  exposed: {', '.join(item.exposed_programs[:4])}"
                f"  |  suppliers {len(item.exposed_suppliers)}"
            )
        if item.analogs:
            a = item.analogs[0]
            typer.echo(f"  analog: {a.name} ({a.similarity:.0%} similar)")
        typer.echo("")
    typer.echo("Use `forgecast report` for the full evidence write-up.")


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
    start: str = typer.Option("2014-01-01"),
    end: str = typer.Option("2023-07-01"),
) -> None:
    """Walk-forward evaluation. Prints Brier score vs a base-rate baseline."""
    from forgecast.backtest import walk_forward
    from forgecast.forecast import WATCHLIST
    from forgecast.sample import generate_world

    world = generate_world()
    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        WATCHLIST,
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
def day(
    home: str = typer.Option(..., help="Home address in metro Atlanta"),
    work: Optional[str] = typer.Option(None, help="Work address"),
    gym: Optional[str] = typer.Option(None, help="Gym or other place"),
) -> None:
    """Live briefing for your Atlanta places. Real GDOT / MARTA / NWS / permits."""
    from forgecast.day import build_day

    raw = [{"label": "home", "address": home}]
    if work:
        raw.append({"label": "work", "address": work})
    if gym:
        raw.append({"label": "gym", "address": gym})
    report = build_day(raw)
    typer.echo(f"Your {report.weekday}  ·  {report.as_of.strftime('%Y-%m-%d %H:%M %Z')}")
    typer.echo(f"feeds: {', '.join(report.sources_ok) or 'none'}")
    if report.sources_failed:
        typer.echo(f"missed: {', '.join(report.sources_failed)}")
    typer.echo("")
    if report.corridor:
        typer.echo(report.corridor)
        typer.echo("")
    if report.routes:
        for route in report.routes:
            flag = f"{route.hits} hits" if route.hits else "clear"
            typer.echo(f"  {route.name}  {route.detail}  {flag}")
        typer.echo("")
    if not report.items:
        typer.echo("Nothing loud on your places. Map still has citywide events.")
        return
    from forgecast.briefing import group_items

    for label, chunk in group_items(report.items):
        typer.echo(label)
        for item in chunk:
            flag = " ↔ " + " / ".join(item.route_names) if item.route_names else ", ".join(item.near)
            typer.echo(f"• {item.advice}")
            typer.echo(f"    {item.kind.value} · {item.source} · {flag}")
            typer.echo("")


@app.command()
def snapshot(
    out: Path = typer.Option(Path("docs"), help="Folder for the static demo site"),
) -> None:
    """Bake live Atlanta events + the map UI. GitHub Pages can host it."""
    from forgecast.snapshot import write_site

    path = write_site(out)
    typer.echo(f"static demo → {out}/  ({path.name})")
    typer.echo("open that folder, or run `forgecast serve`")


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """One process: Atlanta map + live briefing. Open http://127.0.0.1:8000"""
    import uvicorn

    typer.echo(f"Forgecast  →  http://{host}:{port}")
    uvicorn.run("forgecast.api:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
