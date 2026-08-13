from forgecast.routing import (
    downtown_via,
    highways_from_text,
    name_corridor,
    pick_corridors,
    shorter_arc_via,
)
from forgecast.schema import CommuteRoute


def test_i285_is_not_read_as_i85():
    assert highways_from_text("I 285") == ["I-285"]
    assert highways_from_text("I 85") == ["I-85"]
    blob = "I 285 Atlanta Bypass / The Perimeter I 85 Northeast Expressway"
    hw = highways_from_text(blob)
    assert "I-285" in hw
    assert "I-85" in hw
    assert hw.index("I-285") < hw.index("I-85")


def test_name_prefers_perimeter():
    assert name_corridor(["I-85", "I-285"]) == "Perimeter"
    assert name_corridor(["I-85", "I-75"]) == "Connector"
    assert name_corridor(["I-85"]) == "I-85"
    assert name_corridor([]) == "local roads"


def test_briarlake_to_buffington_gets_a_perimeter_via():
    # Briarlake Rd → Chick-fil-A HQ on Buffington Rd
    via = shorter_arc_via(-84.2722, 33.8439, -84.4894, 33.6137)
    assert via is not None
    lon, lat = via
    assert -84.55 < lon < -84.15
    assert 33.62 < lat < 33.92


def test_short_hop_does_not_force_downtown():
    # Ponce → Tech is too short to be an I-85 vs I-285 choice
    assert downtown_via(-84.3652, 33.7724, -84.3963, 33.7756) is None


def test_long_ne_to_south_can_use_downtown_connector():
    via = downtown_via(-84.2722, 33.8439, -84.4894, 33.6137)
    assert via is not None


def test_pick_keeps_distinct_names():
    routes = [
        CommuteRoute(id="perimeter", name="Perimeter", duration_s=42 * 60, kind="shortest"),
        CommuteRoute(id="perimeter-2", name="Perimeter", duration_s=50 * 60, kind="perimeter"),
        CommuteRoute(id="connector", name="Connector", duration_s=43 * 60, kind="alternate"),
    ]
    picked = pick_corridors(routes)
    assert [r.name for r in picked] == ["Perimeter", "Connector"]


def _osrm(ref, name, duration, coords):
    return {
        "duration": duration,
        "distance": duration * 20,
        "geometry": {"coordinates": coords},
        "legs": [{"steps": [{"ref": ref, "name": name}]}],
    }


def test_options_keep_both_named_habits(monkeypatch):
    from forgecast.routing import commute_options

    def fake_fetch(http, points, alternatives=False):
        if not alternatives:
            return []
        return [
            _osrm("I 285", "The Perimeter", 42 * 60, [[-84.27, 33.84], [-84.20, 33.74], [-84.49, 33.61]]),
            _osrm("I 75; I 85", "Downtown Connector", 43 * 60, [[-84.27, 33.84], [-84.39, 33.75], [-84.49, 33.61]]),
        ]

    monkeypatch.setattr("forgecast.routing.fetch_osrm", fake_fetch)
    opts = commute_options(None, -84.2722, 33.8439, -84.4894, 33.6137)
    assert {o.name for o in opts} == {"Perimeter", "Connector"}
    assert all("min" not in (o.detail or "") for o in opts)
