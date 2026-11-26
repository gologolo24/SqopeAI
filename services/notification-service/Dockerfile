# syntax=docker/dockerfile:1

# ---- build stage: install pinned dependencies into an isolated virtualenv ----
FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
# pip is only needed to build: drop it from the venv so it never ships to runtime
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

# ---- runtime stage: only the venv + app code, no build tooling, non-root ----
FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="notification-service" \
      org.opencontainers.image.source="https://github.com/gologolo24/SqopeAI" \
      org.opencontainers.image.revision="${GIT_SHA}"
# 1. Apply Debian security fixes released after the pinned base image was published.
# 2. Remove pip (and its vendored urllib3/msgpack/setuptools, a recurring CVE source):
#    nothing installs packages at runtime, so a package manager is pure attack surface.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.14/ensurepip/_bundled
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_VERSION="${GIT_SHA}"
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
USER 10001:10001
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
