from __future__ import annotations

import time
from typing import Any, Callable, Optional

import requests


def post_xai_chat(
    payload: dict[str, Any],
    xai_key: str | None,
    logger: Any,
    timeout: int = 20,
    context: str = "xai",
    max_retries: int = 2,
    on_rate_limited: Optional[Callable[[], None]] = None,
):
    """Centralized XAI call with retries/backoff and consistent error logging."""
    if not xai_key:
        if logger:
            logger.error(f"{context}: missing XAI key")
        return None

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {xai_key}"},
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            if logger:
                logger.error(f"{context}: request error on attempt {attempt + 1}: {exc}")
            if attempt < max_retries:
                time.sleep(1 + attempt)
            continue

        if response.status_code == 429:
            if logger:
                logger.warning(f"{context}: rate limited (429)")
            if on_rate_limited:
                on_rate_limited()
            continue

        if response.status_code >= 500 and attempt < max_retries:
            if logger:
                logger.warning(f"{context}: server error {response.status_code}, retrying")
            time.sleep(1 + attempt)
            continue

        return response

    return None
