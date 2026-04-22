"""Fase 3: stress_simulator_ohlc op genormaliseerde OHLC-rijen."""

from __future__ import annotations

from lumina_core.evolution.reality_generator import stress_simulator_ohlc
from lumina_core.evolution.simulator_data_support import fallback_synthetic_bars, normalize_simulator_bars


def _sample_bars(n: int = 120) -> list[dict]:
    base = {"net_pnl": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "account_equity": 50_000.0}
    return normalize_simulator_bars(fallback_synthetic_bars(base, n=n))


def test_stress_ohlc_length_and_positives() -> None:
    b = _sample_bars(100)
    s = stress_simulator_ohlc(b, 3, stress_seed="unit_test")
    assert len(s) == len(b)
    for row in s:
        assert float(row["close"]) > 0.0
        assert float(row["high"]) >= float(row["low"])


def test_stress_ohlc_deterministic() -> None:
    b = _sample_bars(80)
    a = stress_simulator_ohlc(b, 2, stress_seed="fixed")
    c = stress_simulator_ohlc(b, 2, stress_seed="fixed")
    assert a[50]["close"] == c[50]["close"]


def test_stress_ohlc_differs_by_reality_id() -> None:
    b = _sample_bars(90)
    s0 = stress_simulator_ohlc(b, 0, stress_seed="x")
    s7 = stress_simulator_ohlc(b, 7, stress_seed="x")
    assert s0[-1]["close"] != s7[-1]["close"]


def test_stress_ohlc_short_list_returns_passthrough() -> None:
    b = [
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "last": 100.0,
        }
    ]
    s = stress_simulator_ohlc(b, 0, stress_seed="y")
    assert len(s) == 1
    assert s[0]["close"] == 100.0
