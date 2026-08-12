from datetime import date

import numpy as np

from forgecast.backtest import walk_forward
from forgecast.features import Entity
from forgecast.forecast import forecast
from forgecast.models import Ensemble
from forgecast.schema import DisruptionType


def test_ensemble_probabilities_in_range():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(80, 17))
    y = (X[:, 3] + X[:, 4] > 0).astype(int)
    y[0] = 0
    y[1] = 1
    model = Ensemble().fit(X, y)
    p = model.predict_proba(X[:10])
    assert p.min() >= 0.005
    assert p.max() <= 0.90


def test_walk_forward_beats_or_matches_baseline(world):
    entities = [
        Entity("CN", "gallium", DisruptionType.EXPORT_RESTRICTION),
        Entity("CN", "rare_earths", DisruptionType.EXPORT_RESTRICTION),
        Entity("RU", "titanium", DisruptionType.EXPORT_RESTRICTION),
        Entity("YE", None, DisruptionType.SHIPPING_THREAT),
        Entity("ID", "nickel", DisruptionType.EXPORT_RESTRICTION),
    ]
    scores, _ = walk_forward(
        world.events,
        world.outcomes,
        entities,
        start=date(2016, 1, 1),
        end=date(2023, 7, 1),
    )
    assert scores.n > 20
    assert scores.brier < 0.35
    # Skill can be small on a tiny watchlist; still must be finite.
    assert scores.baseline_brier >= 0
    assert scores.brier_skill > -0.5


def test_forecast_ties_to_portfolio(world):
    report = forecast(as_of=date(2024, 6, 1), top_n=8)
    assert report.items
    assert all(0 < i.probability < 1 for i in report.items)
    top = report.items[0]
    assert top.drivers
    assert top.would_increase
    assert top.would_decrease
    cn = [i for i in report.items if i.actor_country == "CN"]
    assert cn
    exposed = [i for i in report.items if i.exposed_programs]
    assert exposed
