from __future__ import annotations

from collections import deque
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd

from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent


class _MemoryRecorder:
    """Record append timing while preserving deque-like behavior."""

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.items: deque[dict] = deque(maxlen=50)

    def append(self, item: dict) -> None:
        self.events.append("append")
        self.items.append(item)

    def __len__(self) -> int:
        return len(self.items)


def _build_context(event_log: list[str]) -> SimpleNamespace:
    logger = SimpleNamespace(info=lambda _msg: event_log.append("log"))
    return SimpleNamespace(
        logger=logger,
        get_current_dream_snapshot=lambda: {"signal": "BUY", "confidence": 0.9, "confluence_score": 0.85},
        set_current_dream_fields=lambda _updates: None,
        live_quotes=[{"last": 5100.0}],
        detect_market_regime=lambda _df: "TRENDING",
        ohlc_1min=pd.DataFrame(
            {
                "close": [1.0] * 100,
                "timestamp": pd.date_range("2026-01-01", periods=100, freq="min"),
            }
        ),
        pnl_history=[120.0, 80.0, 100.0, 90.0, 110.0, 95.0],
        trade_log=[{"ts": datetime(2026, 4, 4, 10, 0, 0).isoformat()}],
        equity_curve=[50000.0, 49500.0],
        sim_peak=50000.0,
        account_equity=49500.0,
        market_data=SimpleNamespace(cumulative_delta_10=5000.0),
        current_regime_snapshot={"adaptive_policy": {"emotional_twin_sensitivity": 1.0}},
        config=SimpleNamespace(min_confluence=0.7),
    )


def test_apply_correction_logs_before_memory_append(monkeypatch) -> None:
    events: list[str] = []
    context = _build_context(events)
    twin = EmotionalTwinAgent(context=context)
    twin.memory = cast(Any, _MemoryRecorder(events))

    monkeypatch.setattr("lumina_core.engine.emotional_twin_components.np.random.normal", lambda _m, _s: 0.0)

    result = twin.apply_correction({"signal": "BUY", "confidence": 0.9, "confluence_score": 0.85})
    memory = cast(Any, twin.memory)

    assert events == ["log", "append"]
    assert memory.items[-1]["final_signal"] == result.get("signal", "HOLD")
    assert isinstance(getattr(twin, "_last_bias", {}), dict)


def test_nightly_train_saves_before_logging() -> None:
    events: list[str] = []
    context = _build_context(events)
    twin = EmotionalTwinAgent(context=context)

    twin.logger = SimpleNamespace(info=lambda _msg: events.append("log"))

    saved_payload: dict[str, float] = {}

    def _save(calibration: dict[str, float]) -> None:
        events.append("save")
        saved_payload.update(calibration)

    twin._calibration_store = cast(Any, SimpleNamespace(save=_save))

    updated = twin.nightly_train(
        trade_reflection_history=[{"pnl": -100.0, "reason": "fomo chase"}],
        user_feedback=["tilt behavior"],
    )

    assert events == ["save", "log"]
    assert saved_payload == updated
