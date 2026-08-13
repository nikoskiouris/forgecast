from datetime import date

from forgecast.hexagg import hex_series, week_index, week_to_date


def test_hex_series_has_cells(world):
    series = hex_series(world.events[:400], res=4)
    assert series.h3
    assert len(series.h3) == len(series.week) == len(series.score)
    assert all(s >= 0 for s in series.score)
    w = week_index(date(2026, 6, 1))
    assert week_to_date(w) <= date(2026, 6, 1)
    assert (date(2026, 6, 1) - week_to_date(w)).days < 7
