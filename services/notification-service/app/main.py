"""notification-service: queues email / SMS / Slack notifications for Sqope AI users."""

import logging
import os
import time
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from pythonjsonlogger.json import JsonFormatter

SERVICE_NAME = "notification-service"
VERSION = os.getenv("APP_VERSION", "dev")
QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}

# Structured JSON logs to stdout: the cluster log agent ships them, nothing is written to disk.
_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[_handler], force=True)
logger = logging.getLogger(SERVICE_NAME)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "route"])
QUEUED = Counter("notifications_queued_total", "Notifications queued", ["channel"])

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
    """Readiness: ready to receive traffic (would check the message broker here)."""
    return {"status": "ready", "service": SERVICE_NAME, "version": VERSION}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    SLACK = "slack"


class NotificationIn(BaseModel):
    recipient: str = Field(min_length=1, max_length=200)
    channel: Channel
    message: str = Field(min_length=1, max_length=2000)


class Notification(NotificationIn):
    id: str
    status: str
    queued_at: datetime


# In-memory queue: a real service would publish to SQS/SNS and send from a worker.
_notifications: dict[str, Notification] = {}


@app.post("/notifications", status_code=status.HTTP_202_ACCEPTED)
def queue_notification(payload: NotificationIn) -> Notification:
    notification = Notification(
        id=str(uuid4()),
        status="queued",
        queued_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    _notifications[notification.id] = notification
    QUEUED.labels(payload.channel.value).inc()
    logger.info(
        "notification queued",
        extra={"notification_id": notification.id, "channel": payload.channel.value},
    )
    return notification


@app.get("/notifications")
def list_notifications(recipient: str | None = None) -> list[Notification]:
    items = _notifications.values()
    return [n for n in items if recipient is None or n.recipient == recipient]


@app.get("/notifications/{notification_id}")
def get_notification(notification_id: str) -> Notification:
    notification = _notifications.get(notification_id)
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification not found")
    return notification
