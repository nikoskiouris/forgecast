from datetime import datetime, timedelta

from forgecast.city import (
    EASTERN,
    haversine_km,
    in_metro,
    metro_alert,
    point_to_segment_km,
    station_for_text,
)
from forgecast.geocode import gazetteer_lookup
from forgecast.impact import advice_for, corridor_verdict, impacts
from forgecast.schema import CityEvent, CommuteRoute, EventKind, Place


def test_midtown_is_in_metro():
    assert in_metro(33.78, -84.39)
    assert not in_metro(40.7, -74.0)


def test_haversine_ponce_to_tech_is_a_few_km():
    d = haversine_km(33.7724, -84.3652, 33.7756, -84.3963)
    assert 2 < d < 5


def test_point_to_segment_zero_at_endpoint():
    d = point_to_segment_km(33.75, -84.39, 33.75, -84.39, 33.80, -84.39)
    assert d < 0.05


def test_nws_metro_fulton():
    assert metro_alert("Fulton; DeKalb", ["013121"])
    assert not metro_alert("Chatham; Savannah", ["013051"])


def test_station_match():
    assert station_for_text("Elevator Alert for Peachtree Center Station") is not None
    assert station_for_text("Red Line delays") is not None


def test_gazetteer_ponce():
    hit = gazetteer_lookup("Ponce City Market")
    assert hit is not None
    assert in_metro(hit.lat, hit.lon)


def test_gazetteer_briarlake_and_buffington():
    home = gazetteer_lookup("2855 Brairlake Road")
    work = gazetteer_lookup("5200 Buffinton Road")
    assert home is not None and work is not None
    assert abs(home.lat - 33.8439) < 0.02
    assert abs(work.lat - 33.6137) < 0.02


def _ev(**kw):
    base = {
        "id": "x",
        "kind": EventKind.ROAD,
        "severity": "mid",
        "title": "Lane closure on I-85 at 10th St",
        "lat": 33.781,
        "lon": -84.386,
        "source": "GDOT 511",
    }
    base.update(kw)
    return CityEvent(**base)


def test_commute_and_weather_make_a_briefing():
    home = Place(label="home", address="Ponce City Market", lat=33.7724, lon=-84.3652)
    work = Place(label="work", address="Georgia Tech", lat=33.7756, lon=-84.3963)
    commute = [[home.lon, home.lat], [-84.386, 33.781], [work.lon, work.lat]]
    now = datetime(2026, 8, 13, 9, 0, tzinfo=EASTERN)
    events = [
        _ev(id="road-1", start=now - timedelta(hours=1), end=now + timedelta(days=2)),
        _ev(
            id="wx-1",
            kind=EventKind.WEATHER,
            severity="high",
            title="Severe storms most likely 4–7 PM",
            metro=True,
            lat=33.749,
            lon=-84.388,
            source="Open-Meteo",
        ),
        _ev(
            id="far",
            title="Construction in Rome GA",
            lat=34.25,
            lon=-85.16,
            start=now,
            end=now + timedelta(days=1),
        ),
    ]
    items = impacts(events, [home, work], commute, dest="work", now=now)
    advices = " ".join(i.advice for i in items)
    assert any(i.on_commute or "I-85" in i.advice for i in items)
    assert "storm" in advices.lower() or "Storms" in advices
    assert all("Rome" not in i.title for i in items)


def test_advice_leave_earlier():
    ev = _ev()
    text = advice_for(ev, ["home"], True, "work", "now")
    assert "Leave" in text
    assert "work" in text


def test_corridor_hits_stack_by_usual_habit():
    home = Place(label="home", address="Briarlake Road", lat=33.8439, lon=-84.2722)
    work = Place(label="work", address="Buffington Road", lat=33.6137, lon=-84.4894)
    i85 = CommuteRoute(
        id="i-85",
        name="I-85",
        coords=[[home.lon, home.lat], [-84.386, 33.781], [work.lon, work.lat]],
        kind="shortest",
    )
    i285 = CommuteRoute(
        id="i-285",
        name="I-285",
        coords=[[home.lon, home.lat], [-84.206, 33.746], [work.lon, work.lat]],
        kind="perimeter",
    )
    now = datetime(2026, 8, 13, 9, 0, tzinfo=EASTERN)
    events = [
        _ev(id="on-85", title="Crash on I-85 at 10th St", lat=33.781, lon=-84.386, start=now),
        _ev(id="on-285", title="Lane closure on I-285", lat=33.746, lon=-84.206, start=now),
    ]
    items = impacts(events, [home, work], i85.coords, dest="work", now=now, routes=[i85, i285], usual_id="i-285")
    by = {i.event_id: i for i in items}
    assert "on-285" in by
    assert by["on-285"].tier == "hits"
    assert "I-285" in by["on-285"].advice
    if "on-85" in by:
        assert by["on-85"].tier == "could"
        assert "i-85" in by["on-85"].on_routes
    verdict = corridor_verdict([i85, i285], items, usual_id="i-285")
    assert "I-285" in verdict or "usual" in verdict.lower()
