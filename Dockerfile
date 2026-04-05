# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip wheel setuptools

# Build wheels in a dedicated stage for repeatable, smaller runtime installs.
RUN python -m pip wheel --wheel-dir /wheels \
    numpy \
    pandas \
    requests \
    websockets \
    python-dotenv \
    plotly \
    dash \
    dash-bootstrap-components \
    SpeechRecognition \
    pyttsx3 \
    Pillow \
    fpdf2 \
    chromadb


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    LUMINA_MAX_RESTARTS=5 \
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
RUN python -m pip install --no-index --find-links=/wheels \
    numpy \
    pandas \
    requests \
    websockets \
    python-dotenv \
    plotly \
    dash \
    dash-bootstrap-components \
    SpeechRecognition \
    pyttsx3 \
    Pillow \
    fpdf2 \
    chromadb \
    && rm -rf /wheels

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
