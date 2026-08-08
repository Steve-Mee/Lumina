"""Shared types + pure helpers for birth data pipeline (M5)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from lumina_core.birth.config import BirthCurriculumConfig


class BirthDataPipelineHost(Protocol):
    workspace_root: Path
    birth_config: BirthCurriculumConfig
    market_data_service: Any
    runtime: Any
    birth_start_time: float
    cumulative_trades: int
    ppo_steps: int
    _data_manifest: dict[str, Any]
    _last_raw_ticks_hash: str
    _real_data_pct: float

    def _stop_requested(self) -> bool: ...

    def _emit_birth_progress(self, **kwargs: Any) -> None: ...

    def _notify_history_unavailable(self, detail: str) -> None: ...


@dataclass(slots=True)
class BirthDataPrepareResult:
    ticks: list[dict[str, Any]]
    split: Any | None
    resume_cache_decision: Any | None = None
    resume_skip_load: bool = False
    resume_reenrich_only: bool = False
    early_return: dict[str, Any] | None = None


def generate_synthetic_ticks(n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
    rng = random.Random(51)
    price = max(100.0, float(start_price))
    out: list[dict[str, Any]] = []
    for i in range(max(1, n_ticks)):
        shock = rng.gauss(0.0, 0.0016)
        price = max(10.0, price * (1.0 + shock))
        out.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last": float(price),
                "close": float(price),
                "bid": float(price - 0.125),
                "ask": float(price + 0.125),
                "volume": 1000,
                "regime": "SYNTHETIC",
                "imbalance": 1.0,
                "source": "synthetic",
                "bar_index": i,
            }
        )
    return out


def train_hash(ticks: list[dict[str, Any]]) -> str:
    if not ticks:
        return ""
    head = str(ticks[0].get("timestamp", ""))
    tail = str(ticks[-1].get("timestamp", ""))
    payload = f"{len(ticks)}:{head}:{tail}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


__all__ = [
    "BirthDataPipelineHost",
    "BirthDataPrepareResult",
    "generate_synthetic_ticks",
    "train_hash",
]
