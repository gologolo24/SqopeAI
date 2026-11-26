from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_reports_service_name():
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["service"] == "notification-service"


def test_queue_and_fetch_notification():
    payload = {"recipient": "ops@sqope.ai", "channel": "slack", "message": "deploy finished"}
    queued = client.post("/notifications", json=payload)
    assert queued.status_code == 202
    body = queued.json()
    assert body["status"] == "queued"

    fetched = client.get(f"/notifications/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["channel"] == "slack"


def test_filter_by_recipient():
    for recipient, channel in [("a@sqope.ai", "email"), ("b@sqope.ai", "sms")]:
        payload = {"recipient": recipient, "channel": channel, "message": "hi"}
        client.post("/notifications", json=payload)
    only_a = client.get("/notifications", params={"recipient": "a@sqope.ai"}).json()
    assert only_a
    assert all(n["recipient"] == "a@sqope.ai" for n in only_a)


def test_unsupported_channel_is_rejected():
    payload = {"recipient": "x@sqope.ai", "channel": "fax", "message": "hi"}
    assert client.post("/notifications", json=payload).status_code == 422


def test_unknown_notification_returns_404():
    assert client.get("/notifications/does-not-exist").status_code == 404


def test_metrics_count_per_channel():
    body = client.get("/metrics").text
    assert 'notifications_queued_total{channel="slack"}' in body
