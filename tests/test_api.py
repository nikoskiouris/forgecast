from fastapi.testclient import TestClient

from forgecast.api import app

client = TestClient(app)


def test_health_and_meta():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["product"] == "Gridpulse"
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["product"] == "Gridpulse"
