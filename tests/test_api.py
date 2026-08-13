from datetime import datetime

from fastapi.testclient import TestClient

from forgecast.api import app
from forgecast.city import EASTERN
from forgecast.schema import CityBundle, CityEvent, EventKind
from forgecast.snapshot import write_site

client = TestClient(app)


def fake_bundle() -> CityBundle:
    now = datetime(2026, 8, 13, 10, 0, tzinfo=EASTERN)
    return CityBundle(
        as_of=now,
        events=[
            CityEvent(
                id="gdot:1",
                kind=EventKind.EVENT,
                severity="high",
                title="Sporting event on North Ave",
                summary="Major event near State Farm Arena",
                lat=33.7717,
                lon=-84.3867,
                source="GDOT 511",
                source_url="https://511ga.org/",
                raw_type="major event",
            ),
            CityEvent(
                id="om:1",
                kind=EventKind.WEATHER,
                severity="mid",
                title="Rain likely 4–7 PM",
                summary="Rain chances peak around 60%.",
                lat=33.749,
                lon=-84.388,
                source="Open-Meteo",
                metro=True,
            ),
        ],
        notes=["test feeds"],
        sources_ok=["gdot:1", "open-meteo:1"],
        sources_failed=[],
    )


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert res.json()["city"] == "Atlanta"


def test_ui_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "What could disrupt your day?" in res.text
    assert "Enter an Atlanta" in res.text or "Atlanta address" in res.text


def test_events_and_day(monkeypatch):
    bundle = fake_bundle()
    monkeypatch.setattr("forgecast.api.live_bundle", lambda force=False: bundle)
    res = client.get("/api/events")
    assert res.status_code == 200
    body = res.json()
    assert body["events"]
    assert body["events"][0]["lat"] is not None

    day = client.get("/api/day?home=Ponce%20City%20Market")
    assert day.status_code == 200
    report = day.json()
    assert report["places"][0]["label"] == "home"
    assert report["items"]
    assert any(i["kind"] == "weather" for i in report["items"])


def test_snapshot_roundtrip(tmp_path):
    path = write_site(tmp_path, fake_bundle())
    assert path.exists()
    assert (tmp_path / "index.html").is_file()
    text = (tmp_path / "index.html").read_text()
    assert "What could disrupt your day?" in text
    raw = path.read_text()
    assert "gdot:1" in raw
    assert "dummy" not in raw.lower()
