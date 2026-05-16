"""HTTP helpers for Streamlit frontend — quiet logs when the backend is offline."""

from __future__ import annotations

import logging
from typing import Any

import requests

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


def is_backend_unreachable(exc: BaseException) -> bool:
    """True when the FastAPI backend is down or not reachable (expected in local UI)."""
    if isinstance(exc, requests.exceptions.ConnectionError | requests.exceptions.Timeout):
        return True
    if httpx is not None and isinstance(
        exc,
        httpx.ConnectError | httpx.ConnectTimeout | httpx.ReadTimeout | httpx.WriteTimeout,
    ):
        return True
    if httpx is not None and isinstance(exc, httpx.RequestError) and not isinstance(
        exc, httpx.HTTPStatusError
    ):
        return True
    return False


def log_fetch_failure(logger: logging.Logger, message: str, exc: BaseException) -> None:
    """Log at debug when backend is offline; warn with traceback for unexpected failures."""
    if is_backend_unreachable(exc):
        logger.debug("%s (backend offline): %s", message, exc)
    else:
        logger.warning("%s: %s", message, exc, exc_info=True)


def fetch_json(
    url: str,
    *,
    timeout: float = 5.0,
    headers: dict[str, str] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any] | list[Any] | None:
    """GET JSON; returns None on failure without noisy exception logs when backend is down."""
    log = logger or logging.getLogger(__name__)
    try:
        response = requests.get(url, headers=headers or {}, timeout=timeout)
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]
    except Exception as exc:
        log_fetch_failure(log, f"GET {url}", exc)
        return None
