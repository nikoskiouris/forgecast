from datetime import date

from forgecast.analogs import analog_summary, cosine, window_vector
from forgecast.features import FEATURE_NAMES, feature_vector, label_for
from forgecast.schema import Entity, SignalType


def test_world_has_signal(world):
    assert len(world.events) > 1000
    assert any(o.geo_id == "ERCO-W" for o in world.outcomes)
    assert any("ERCOT-West 2025" in o.name for o in world.outcomes)


def test_feature_length(world):
    ent = Entity("ERCO-W", "ba", SignalType.LOAD_GROWTH)
    x = feature_vector(world.events, ent, date(2025, 6, 1))
    assert len(x) == len(FEATURE_NAMES)
    assert x[FEATURE_NAMES.index("n_90")] >= 0


def test_label_positive_inside_horizon(world):
    ent = Entity("ERCO-W", "ba", SignalType.LOAD_GROWTH)
    assert label_for(ent, date(2025, 2, 1), world.outcomes, 180) == 1
    assert label_for(ent, date(2024, 1, 1), world.outcomes, 180) == 0


def test_analogs_retrieve_named_episode(world):
    ent = Entity("51047", "county", SignalType.GIGA_SITE)
    summary = analog_summary(world.events, ent, date(2026, 6, 1), world.outcomes, k=3)
    assert summary.matches
    assert summary.max_similarity >= 0.35
    names = " ".join(m.name.lower() for m in summary.matches)
    assert "giga" in names or "loudoun" in names or "abilene" in names or "clark" in names


def test_cosine_identical():
    import numpy as np

    v = np.ones(5)
    assert abs(cosine(v, v) - 1.0) < 1e-6
    assert window_vector([], date(2020, 1, 1), date(2020, 2, 1)).shape[0] > 5
