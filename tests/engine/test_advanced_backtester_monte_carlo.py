"""Monte Carlo mode: strict config uses historical sub-windows only (no OHLC noise)."""
from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from lumina_core.engine.advanced_backtester_engine import AdvancedBacktesterEngine, _monte_carlo_work_frame
from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.realistic_backtester_engine import RealisticBacktesterEngine
from lumina_core.runtime_context import RuntimeContext


def _is_contiguous_price_slice(sub: np.ndarray, full: np.ndarray) -> bool:
    if len(sub) > len(full):
        return False
    for i in range(len(full) - len(sub) + 1):
        if np.allclose(full[i : i + len(sub)], sub, rtol=0, atol=0):
            return True
    return False


def test_full_monte_carlo_historical_bootstrap_subsamples_real_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.engine.advanced_backtester_engine.require_real_simulator_data_strict",
        lambda: True,
    )

    engine = LuminaEngine(config=EngineConfig())
    ctx = RuntimeContext(engine=engine)
    advanced = AdvancedBacktesterEngine(ctx)

    stub_metrics = {
        "sharpe": 1.0,
        "maxdd": 2.0,
        "winrate": 0.5,
        "trades": 3,
        "profit_factor": 1.1,
        "avg_pnl": 0.0,
    }

    captured: list[pd.DataFrame] = []

    def fake_run(snapshot: pd.DataFrame) -> dict:
        captured.append(snapshot.copy())
        return dict(stub_metrics)

    mock_realistic = MagicMock(spec=RealisticBacktesterEngine)
    mock_realistic.run_backtest_on_snapshot = fake_run
    advanced.realistic = cast(RealisticBacktesterEngine, mock_realistic)

    n = 180
    prices = np.linspace(5000.0, 5010.0, n)
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=n, freq="min"),
            "open": prices,
            "high": prices + 0.25,
            "low": prices - 0.25,
            "close": prices,
            "volume": 1000,
        }
    )

    out = advanced.full_monte_carlo(df, runs=15)
    assert out["monte_carlo_mode"] == "historical_bootstrap"
    assert out["num_runs"] == 15
    assert len(captured) == 15
    full_close = df["close"].to_numpy()
    for snap in captured:
        assert _is_contiguous_price_slice(snap["close"].to_numpy(), full_close)
    assert len(out["_sharpe_samples"]) == 15


def test_full_monte_carlo_insufficient_rows_returns_empty_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.engine.advanced_backtester_engine.require_real_simulator_data_strict",
        lambda: True,
    )
    engine = LuminaEngine(config=EngineConfig())
    ctx = RuntimeContext(engine=engine)
    advanced = AdvancedBacktesterEngine(ctx)
    stub = MagicMock(spec=RealisticBacktesterEngine)
    stub.run_backtest_on_snapshot = lambda _s: {}
    advanced.realistic = cast(RealisticBacktesterEngine, stub)

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=50, freq="min"),
            "close": np.linspace(100.0, 101.0, 50),
            "volume": 1,
        }
    )
    out = advanced.full_monte_carlo(df, runs=100)
    assert out["num_runs"] == 0
    assert out["monte_carlo_mode"] == "historical_bootstrap_insufficient_data"


def test_monte_carlo_work_frame_reset_index() -> None:
    idx = pd.date_range("2024-01-01", periods=5, freq="h")
    df = pd.DataFrame({"close": [1, 2, 3, 4, 5], "volume": 1}, index=idx)
    work = _monte_carlo_work_frame(df)
    assert "timestamp" in work.columns
    assert len(work) == 5
