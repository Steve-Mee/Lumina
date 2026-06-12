"""HTTP helpers for monitoring clients — quiet logs when the backend is offline."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

_API_KEY_NAMES = (
    "LUMINA_ADMIN_API_KEY",
    "LUMINA_BACKEND_API_KEY",
    "LUMINA_DASHBOARD_API_KEY",
    "X_API_KEY",
)


def _repo_root() -> Path:
    config_path = str(os.getenv("LUMINA_CONFIG", "")).strip()
    if config_path:
        return Path(config_path).expanduser().resolve().parent
    here = Path(__file__).resolve()
    for candidate in (Path.cwd(), here.parents[2], here.parents[1]):
        if (candidate / "config.yaml").exists() and (candidate / "lumina_os").exists():
            return candidate.resolve()
    return Path.cwd().resolve()


@lru_cache(maxsize=1)
def _read_repo_dotenv() -> dict[str, str]:
    env_path = _repo_root() / ".env"
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_dashboard_api_key(explicit: str = "") -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    for name in _API_KEY_NAMES:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    dotenv_values = _read_repo_dotenv()
    for name in _API_KEY_NAMES:
        value = str(dotenv_values.get(name, "")).strip()
        if value:
            return value
    return ""


def is_backend_unreachable(exc: BaseException) -> bool:
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
    log = logger or logging.getLogger(__name__)
    try:
        response = requests.get(url, headers=headers or {}, timeout=timeout)
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]
    except Exception as exc:
        log_fetch_failure(log, f"GET {url}", exc)
        return None
