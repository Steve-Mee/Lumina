"""Latency SLA for FAST_PATH_ONLY triggers (market-data websocket vs reasoning inference).

Environment (launcher writes ``LUMINA_LATENCY_SLA_MS`` for both unless overridden):

- ``LUMINA_LATENCY_SLA_MS`` — single knob (ms) applied to market-data and reasoning when specifics unset.
- ``LUMINA_MARKET_DATA_SLA_MS`` — overrides unified value for websocket tick latency (default 250).
- ``LUMINA_REASONING_SLA_MS`` — overrides unified value for inference latency (default 300).

Bounds: 50 ms … 600000 ms (10 min).
"""

from __future__ import annotations

import os


def _env_float(name: str, *, fallback: float, min_v: float = 50.0, max_v: float = 600_000.0) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        return max(min_v, min(max_v, float(str(raw).strip())))
    except ValueError:
        return fallback


def market_data_latency_sla_ms() -> float:
    """Websocket / tick path (``MarketDataService``)."""
    if os.getenv("LUMINA_MARKET_DATA_SLA_MS", "").strip() != "":
        return _env_float("LUMINA_MARKET_DATA_SLA_MS", fallback=250.0)
    return _env_float("LUMINA_LATENCY_SLA_MS", fallback=250.0)


def reasoning_latency_sla_ms() -> float:
    """LLM / inference path (``ReasoningService``)."""
    if os.getenv("LUMINA_REASONING_SLA_MS", "").strip() != "":
        return _env_float("LUMINA_REASONING_SLA_MS", fallback=300.0)
    return _env_float("LUMINA_LATENCY_SLA_MS", fallback=300.0)
