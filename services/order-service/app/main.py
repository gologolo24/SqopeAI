"""order-service: creates and tracks customer orders on the Sqope AI platform."""

import logging
import os
import time
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from pythonjsonlogger.json import JsonFormatter

SERVICE_NAME = "order-service"
VERSION = os.getenv("APP_VERSION", "dev")
QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}

# Structured JSON logs to stdout: the cluster log agent ships them, nothing is written to disk.
_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[_handler], force=True)
logger = logging.getLogger(SERVICE_NAME)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "route"])
ORDERS = Counter("orders_created_total", "Orders created")

app = FastAPI(title=SERVICE_NAME, version=VERSION)


@app.middleware("http")
async def observe(request: Request, call_next):
    """Record RED metrics (rate, errors, duration) and a JSON access log per request."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    path = route.path if route else "unmatched"  # route template keeps label cardinality low
    REQUESTS.labels(request.method, path, response.status_code).inc()
    LATENCY.labels(request.method, path).observe(elapsed)
    if request.url.path not in QUIET_PATHS:
        logger.info(
            "request",
            extra={
                "method": request.method,
                "route": path,
                "status": response.status_code,
                "duration_ms": round(elapsed * 1000, 2),
            },
        )
    return response


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
def readyz() -> dict:
    """Readiness: ready to receive traffic (would check DB/queue connections here)."""
    return {"status": "ready", "service": SERVICE_NAME, "version": VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class OrderItem(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0, le=1000)
    unit_price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class OrderIn(BaseModel):
    user_id: str = Field(min_length=1)
    items: list[OrderItem] = Field(min_length=1)


class Order(OrderIn):
    id: str
    status: str
    total: Decimal


# In-memory store: enough for the demo; a real service would use a managed database.
_orders: dict[str, Order] = {}


@app.post("/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderIn) -> Order:
    total = sum((item.unit_price * item.quantity for item in payload.items), Decimal("0"))
    order = Order(id=str(uuid4()), status="created", total=total, **payload.model_dump())
    _orders[order.id] = order
    ORDERS.inc()
    logger.info("order created", extra={"order_id": order.id, "total": str(total)})
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str) -> Order:
    order = _orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
    return order
