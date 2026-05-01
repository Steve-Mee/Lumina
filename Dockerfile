# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip wheel setuptools

COPY requirements-core.txt requirements-trading.txt /build/

# Build wheels in a dedicated stage for repeatable, smaller runtime installs.
RUN python -m pip wheel --wheel-dir /wheels \
    -r requirements-core.txt \
    -r requirements-trading.txt


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LUMINA_MAX_RESTARTS=5 \
    LUMINA_ENTRYPOINT=lumina_core/engine/runtime_entrypoint.py \
    LUMINA_ENTRYPOINT_ARGS="--mode auto" \
    LUMINA_HEALTH_MAX_AGE=120

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini \
        ca-certificates \
        curl \
        espeak-ng \
        libespeak1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements-core.txt /tmp/requirements-core.txt
COPY --from=builder /build/requirements-trading.txt /tmp/requirements-trading.txt
RUN python -m pip install --no-index --find-links=/wheels \
    -r /tmp/requirements-core.txt \
    -r /tmp/requirements-trading.txt \
    && rm -rf /wheels /tmp/requirements-core.txt /tmp/requirements-trading.txt

COPY . /app

RUN groupadd --system lumina \
    && useradd --system --gid lumina --uid 10001 --create-home --home-dir /home/lumina lumina \
    && mkdir -p /app/state /app/journal /app/lumina_vector_db /app/logs \
    && chown -R lumina:lumina /app /home/lumina

USER lumina

# Healthcheck validates watchdog heartbeat freshness written by watchdog.py.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import os,time,pathlib,sys; p=pathlib.Path('/tmp/lumina_heartbeat'); m=float(os.getenv('LUMINA_HEALTH_MAX_AGE','120')); sys.exit(0 if p.exists() and (time.time()-p.stat().st_mtime)<m else 1)"

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "watchdog.py"]
