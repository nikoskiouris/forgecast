"""Forecast engine: as-of cutoff, ensemble probabilities, analogs, exposure."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from forgecast.analogs import analog_summary
from forgecast.backtest import build_xy
from forgecast.config import DEFAULT_HORIZON_DAYS, DEFAULT_PORTFOLIO, DEMO_AS_OF
from forgecast.explain import THRESHOLDS, drivers_from_features, fill_text_fields, recent_sources
from forgecast.exposure import apply_exposure, load_portfolio
from forgecast.features import Entity, feature_vector, horizon_for, month_starts
from forgecast.geo import cell_for, make_pin_id
from forgecast.graph import Store
from forgecast.models import Ensemble
from forgecast.sample import generate_world
from forgecast.schema import Event, ForecastItem, ForecastReport, Outcome
from forgecast.staticdata import coords, place_name, train_watchlist, watchlist

WATCHLIST: list[Entity] = watchlist()
TRAIN_WATCH: list[Entity] = train_watchlist()


def load_training_world(store: Store | None = None) -> tuple[list[Event], list[Outcome]]:
    world = generate_world()
    if store is None or store.count() == 0:
        return world.events, world.outcomes
    live = store.events_as_of(date.today(), lookback_days=365 * 20)
    if live:
        return live, world.outcomes
    return world.events, world.outcomes


@lru_cache(maxsize=4)
def _cached_model(as_of: date) -> Ensemble:
    events, outcomes = load_training_world()
    return fit_model(events, outcomes, as_of)


def fit_model(events: list[Event], outcomes: list[Outcome], as_of: date) -> Ensemble:
    train_end = as_of - timedelta(days=DEFAULT_HORIZON_DAYS + 1)
    start = date(2014, 1, 1)
    if train_end <= start:
        train_end = date(2018, 1, 1)
    dates = month_starts(start, train_end)
    dates = [d for d in dates if d.month in {1, 4, 7, 10}]
    X, y, _ = build_xy(events, outcomes, TRAIN_WATCH, dates, DEFAULT_HORIZON_DAYS)
    return Ensemble().fit(X, y)


def _item_for(
    model: Ensemble,
    events: list[Event],
    outcomes: list[Outcome],
    entity: Entity,
    as_of: date,
    prev_as_of: date,
    portfolio: dict,
) -> ForecastItem:
    known = [e for e in events if e.timestamp.date() <= as_of]
    analog = analog_summary(known, entity, as_of, outcomes)
    x = feature_vector(known, entity, as_of, analog.rate, analog.max_similarity)
    p = float(model.predict_proba(x.reshape(1, -1))[0])

    known_prev = [e for e in events if e.timestamp.date() <= prev_as_of]
    analog_p = analog_summary(known_prev, entity, prev_as_of, outcomes)
    xp = feature_vector(known_prev, entity, prev_as_of, analog_p.rate, analog_p.max_similarity)
    p_prev = float(model.predict_proba(xp.reshape(1, -1))[0])

    lat, lon = coords(entity.geo_id)
    item = ForecastItem(
        id=make_pin_id(entity.geo_id, entity.signal),
        signal_type=entity.signal,
        geo_id=entity.geo_id,
        geo_kind=entity.geo_kind,
        geo_name=place_name(entity.geo_id),
        site=place_name(entity.geo_id),
        lat=lat,
        lon=lon,
        h3=cell_for(lat, lon, 5),
        threshold=THRESHOLDS[entity.signal],
        probability=round(p, 4),
        previous_probability=round(p_prev, 4),
        delta=round(p - p_prev, 4),
        drivers=drivers_from_features(x, known, entity),
        analogs=analog.matches,
        sources=recent_sources(known, entity),
    )
    item = fill_text_fields(item)
    return apply_exposure(item, portfolio)


def forecast(
    as_of: date | None = None,
    horizon_days: int = DEFAULT_HORIZON_DAYS,
    portfolio_path: Path | None = None,
    store: Store | None = None,
    model: Ensemble | None = None,
    top_n: int = 16,
) -> ForecastReport:
    as_of = as_of or DEMO_AS_OF
    portfolio_path = portfolio_path or DEFAULT_PORTFOLIO
    portfolio = (
        load_portfolio(portfolio_path)
        if portfolio_path.exists()
        else {"name": "none", "holdings": []}
    )
    events, outcomes = load_training_world(store)
    if model is None:
        model = _cached_model(as_of) if store is None else fit_model(events, outcomes, as_of)
    prev = as_of - timedelta(days=30)
    # Score the hot subset plus a few more so the map is not empty.
    score_list = list(TRAIN_WATCH)
    seen = {(e.geo_id, e.signal) for e in score_list}
    for ent in WATCHLIST:
        if (ent.geo_id, ent.signal) not in seen:
            # Keep inference bounded: remaining BAs only.
            if ent.geo_kind == "ba":
                score_list.append(ent)
                seen.add((ent.geo_id, ent.signal))
    items = [_item_for(model, events, outcomes, ent, as_of, prev, portfolio) for ent in score_list]
    items.sort(key=lambda i: i.probability, reverse=True)
    notes = [
        "Publisher, not an adviser. Mechanical ticker exposure is not a recommendation.",
        "Probabilities are calibrated ensemble outputs, not declarations that an event will happen.",
        "GDELT is attention only and never a label. Sample-world backtests prove the pipeline.",
    ]
    return ForecastReport(
        as_of=as_of,
        horizon_days=horizon_days,
        portfolio=portfolio.get("name", "gridpulse-demo"),
        items=items[:top_n],
        notes=notes,
    )


def item_horizon(item: ForecastItem, default: int = DEFAULT_HORIZON_DAYS) -> int:
    return horizon_for(item.signal_type, default)
