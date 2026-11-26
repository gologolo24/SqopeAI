"""user-service: manages users of the Sqope AI platform."""

import logging
import os
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from pythonjsonlogger.json import JsonFormatter

SERVICE_NAME = "user-service"
VERSION = os.getenv("APP_VERSION", "dev")
QUIET_PATHS = {"/healthz", "/readyz", "/metrics"}

# Structured JSON logs to stdout: the cluster log agent ships them, nothing is written to disk.
_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), handlers=[_handler], force=True)
logger = logging.getLogger(SERVICE_NAME)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP latency", ["method", "route"])

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


class UserIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class User(UserIn):
    id: str


# In-memory store: enough for the demo; a real service would use a managed database.
_users: dict[str, User] = {}


@app.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserIn) -> User:
    user = User(id=str(uuid4()), **payload.model_dump())
    _users[user.id] = user
    logger.info("user created", extra={"user_id": user.id})
    return user


@app.get("/users")
def list_users() -> list[User]:
    return list(_users.values())


@app.get("/users/{user_id}")
def get_user(user_id: str) -> User:
    user = _users.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user
