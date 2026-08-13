from datetime import date

from forgecast.forecast import forecast
from forgecast.geo import build_map


def test_forecast_pins_carry_coordinates():
    report = forecast(as_of=date(2024, 6, 1), top_n=16)
    assert report.items
    for item in report.items:
        assert item.id
        assert item.lat is not None
        assert item.lon is not None
        assert item.site
    payload = build_map(report)
    assert len(payload.pins) == len(report.items)
    assert payload.pins[0].headline
    assert payload.suppliers
