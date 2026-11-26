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
    assert response.json()["service"] == "order-service"


def test_create_order_computes_total():
    payload = {
        "user_id": "u-1",
        "items": [
            {"sku": "plan-pro", "quantity": 2, "unit_price": "49.90"},
            {"sku": "addon-seat", "quantity": 3, "unit_price": "5.00"},
        ],
    }
    created = client.post("/orders", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "created"
    assert body["total"] == "114.80"

    fetched = client.get(f"/orders/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["user_id"] == "u-1"


def test_order_without_items_is_rejected():
    response = client.post("/orders", json={"user_id": "u-1", "items": []})
    assert response.status_code == 422


def test_unknown_order_returns_404():
    assert client.get("/orders/does-not-exist").status_code == 404


def test_metrics_expose_business_counter():
    body = client.get("/metrics").text
    assert "orders_created_total" in body
    assert "http_requests_total" in body
