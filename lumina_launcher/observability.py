"""Launcher-level structured logging helpers."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("lumina_launcher.observability")


def ensure_run_id(session_state: Any) -> str:
    run_id = session_state.get("lumina_run_id")
    if not isinstance(run_id, str) or not run_id:
        run_id = uuid.uuid4().hex[:10]
        session_state["lumina_run_id"] = run_id
    counter = int(session_state.get("lumina_run_seq", 0) or 0) + 1
    session_state["lumina_run_seq"] = counter
    return run_id


def log_event(event: str, level: int = logging.INFO, **payload: Any) -> None:
    parts = [f"event={event}"]
    parts.extend(f"{k}={payload[k]}" for k in sorted(payload))
    logger.log(level, " ".join(parts))


@contextmanager
def timed_event(event: str, **base_payload: Any):
    started = time.perf_counter()
    try:
        yield
    except Exception:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_event(event, level=logging.ERROR, duration_ms=elapsed_ms, status="error", **base_payload)
        raise
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    log_event(event, duration_ms=elapsed_ms, status="ok", **base_payload)


def timed_call(event: str, fn: Callable[[], Any], **payload: Any) -> Any:
    with timed_event(event, **payload):
        return fn()
