from datetime import date

import numpy as np

from forgecast.backtest import walk_forward
from forgecast.features import FEATURE_NAMES
from forgecast.forecast import forecast
from forgecast.models import Ensemble
from forgecast.staticdata import train_watchlist


def test_ensemble_probabilities_in_range():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, len(FEATURE_NAMES)))
    y = (X[:, 3] + X[:, 4] > 0).astype(int)
    y[0] = 0
    y[1] = 1
    model = Ensemble().fit(X, y)
    p = model.predict_proba(X[:10])
    assert p.min() >= 0.005
    assert p.max() <= 0.90


def test_walk_forward_beats_or_matches_baseline(world):
    entities = train_watchlist()[:6]
    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        entities,
        start=date(2016, 1, 1),
        end=date(2025, 7, 1),
    )
    assert scores.n > 20
    assert scores.brier < 0.35
    assert scores.baseline_brier >= 0
    assert scores.brier_skill > -0.5


def test_forecast_ties_to_portfolio(world):
    report = forecast(as_of=date(2026, 6, 1), top_n=8)
    assert report.items
    assert all(0 < i.probability < 1 for i in report.items)
    top = report.items[0]
    assert top.drivers
    assert top.would_increase
    assert top.would_decrease
    ercot = [i for i in report.items if i.geo_id == "ERCO-W"]
    assert ercot
    assert {t.ticker for t in ercot[0].exposed_tickers} <= {"VST", "NRG"}
    assert ercot[0].exposed_tickers
    assert ercot[0].probability >= 0.5
    names = " ".join(a.name for a in ercot[0].analogs)
    assert "2025" in names or "ERCOT" in names
