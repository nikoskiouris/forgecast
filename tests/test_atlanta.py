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
from forgecast.impact import advice_for, impacts
from forgecast.schema import CityEvent, EventKind, Place


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
