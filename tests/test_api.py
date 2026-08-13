from fastapi.testclient import TestClient

from forgecast.api import app

client = TestClient(app)


def test_health():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_ui_index():
    res = client.get("/")
    assert res.status_code == 200
    assert "Forgecast" in res.text


def test_map_snapshot():
    demo = client.get("/data/demo.json")
    assert demo.status_code == 200
    bundle = demo.json()
    assert "2024-06-01" in bundle["snapshots"]
    res = client.get("/api/map?as_of=2024-06-01")
    assert res.status_code == 200
    body = res.json()
    assert body["pins"]
    assert body["pins"][0]["lat"] is not None
    assert body["pins"][0]["headline"]
