"""Walk-forward backtest with Brier score, log loss, and a base-rate baseline."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from forgecast.analogs import analog_summary
from forgecast.features import Entity, feature_vector, label_for, month_starts
from forgecast.models import Ensemble
from forgecast.schema import BacktestScores, Event, Outcome


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


def _reliability(y: np.ndarray, p: np.ndarray, bins: int = 8) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    rows = []
    for i in range(bins):
        mask = (p >= edges[i]) & (p < edges[i + 1] if i < bins - 1 else p <= edges[i + 1])
        if not np.any(mask):
            continue
        rows.append(
            {
                "bin": f"{edges[i]:.2f}-{edges[i + 1]:.2f}",
                "n": int(mask.sum()),
                "forecast": float(p[mask].mean()),
                "observed": float(y[mask].mean()),
            }
        )
    return rows


def build_xy(
    events: list[Event],
    outcomes: list[Outcome],
    entities: list[Entity],
    as_of_dates: list[date],
    horizon_days: int,
) -> tuple[np.ndarray, np.ndarray, list[tuple[date, Entity]]]:
    by_geo: dict[str, list[Event]] = {}
    for e in events:
        if e.geo_id:
            by_geo.setdefault(e.geo_id, []).append(e)
    xs = []
    ys = []
    keys = []
    for as_of in as_of_dates:
        for ent in entities:
            scoped = [e for e in by_geo.get(ent.geo_id, []) if e.timestamp.date() <= as_of]
            analog = analog_summary(scoped, ent, as_of, outcomes)
            x = feature_vector(scoped, ent, as_of, analog.rate, analog.max_similarity)
            y = label_for(ent, as_of, outcomes, horizon_days)
            xs.append(x)
            ys.append(y)
            keys.append((as_of, ent))
    return np.vstack(xs), np.asarray(ys, dtype=int), keys


def walk_forward(
    events: list[Event],
    outcomes: list[Outcome],
    entities: list[Entity],
    horizon_days: int = 180,
    start: date = date(2014, 1, 1),
    end: date = date(2025, 7, 1),
    months: tuple[int, ...] = (1, 4, 7, 10),
) -> tuple[BacktestScores, Ensemble]:
    dates = [d for d in month_starts(start, end) if d.month in months]
    X, y, keys = build_xy(events, outcomes, entities, dates, horizon_days)

    preds = np.zeros(len(y))
    last_model = Ensemble()
    years = sorted({d.year for d, _ in keys})
    for year in years:
        train_idx = []
        test_idx = []
        for i, (as_of, _) in enumerate(keys):
            label_known_by = as_of + timedelta(days=horizon_days)
            if label_known_by < date(year, 1, 1) and as_of.year < year:
                train_idx.append(i)
            if as_of.year == year:
                test_idx.append(i)
        if len(train_idx) < 15 or not test_idx:
            continue
        model = Ensemble().fit(X[train_idx], y[train_idx])
        preds[test_idx] = model.predict_proba(X[test_idx])
        last_model = model

    scored_mask = preds > 0
    if not np.any(scored_mask):
        last_model = Ensemble().fit(X, y)
        preds = last_model.predict_proba(X)
        scored_mask = np.ones(len(y), dtype=bool)

    yt, pt = y[scored_mask], preds[scored_mask]
    base = float(yt.mean()) if len(yt) else 0.0
    brier = _brier(yt, pt)
    baseline_brier = _brier(yt, np.full_like(pt, base, dtype=float))
    skill = 1.0 - brier / baseline_brier if baseline_brier > 0 else 0.0
    scores = BacktestScores(
        n=int(len(yt)),
        brier=brier,
        log_loss=_log_loss(yt, pt),
        base_rate=base,
        baseline_brier=baseline_brier,
        brier_skill=skill,
        reliability=_reliability(yt, pt),
    )
    return scores, last_model
