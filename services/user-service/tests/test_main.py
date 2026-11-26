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
    assert response.json()["service"] == "user-service"


def test_create_and_get_user():
    created = client.post("/users", json={"name": "Dana", "email": "dana@sqope.ai"})
    assert created.status_code == 201
    user_id = created.json()["id"]

    fetched = client.get(f"/users/{user_id}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == "dana@sqope.ai"
    assert any(u["id"] == user_id for u in client.get("/users").json())


def test_unknown_user_returns_404():
    assert client.get("/users/does-not-exist").status_code == 404


def test_invalid_email_is_rejected():
    response = client.post("/users", json={"name": "Dana", "email": "not-an-email"})
    assert response.status_code == 422


def test_metrics_use_route_template_label():
    client.get("/users/some-id")
    body = client.get("/metrics").text
    assert 'route="/users/{user_id}"' in body
    assert "http_request_duration_seconds" in body
