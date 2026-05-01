"""Tests for DynamicKellyEstimator (P7 - Financial Modeling Completeness).

All tests are unit-level: no I/O, no external services.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from lumina_core.engine.dynamic_kelly import DynamicKellyEstimator, _MIN_WINDOW_TRADES
from lumina_core.engine.financial_contracts import DynamicKellyContract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_estimator(tmp_path: Path, window: int = 50) -> DynamicKellyEstimator:
    return DynamicKellyEstimator(
        window=window,
        min_kelly=0.01,
        fractional_kelly_real=0.25,
        fractional_kelly_sim=1.0,
        config_fallback_real=0.25,
        config_fallback_sim=1.0,
        history_path=tmp_path / "kelly_history.jsonl",
    )


def _feed_trades(estimator: DynamicKellyEstimator, wins: int, losses: int, avg_win: float = 200.0, avg_loss: float = 100.0) -> None:
    for _ in range(wins):
        estimator.record_trade(avg_win)
    for _ in range(losses):
        estimator.record_trade(-avg_loss)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDynamicKellyEstimator:
    def test_fallback_before_sufficient_trades(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        # Feed fewer than min window trades
        for _ in range(_MIN_WINDOW_TRADES - 1):
            est.record_trade(100.0)
        # Should return config fallback
        assert est.fractional_kelly("real") == pytest.approx(0.25, rel=1e-3)

    def test_kelly_increases_with_good_winrate(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        # 70% win rate, 2:1 reward-to-risk → raw Kelly ≈ 0.55
        _feed_trades(est, wins=35, losses=15, avg_win=200.0, avg_loss=100.0)
        raw = est.raw_kelly()
        assert raw > 0.3, f"Expected raw Kelly > 0.3 for high win-rate, got {raw:.3f}"

    def test_kelly_capped_in_real_mode(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        # Extremely profitable — raw Kelly would be > cap
        _feed_trades(est, wins=45, losses=5, avg_win=1000.0, avg_loss=50.0)
        frac = est.fractional_kelly("real")
        assert frac <= 0.25, f"REAL mode Kelly must not exceed 0.25, got {frac:.3f}"

    def test_kelly_allows_higher_in_sim(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=40, losses=10, avg_win=300.0, avg_loss=100.0)
        real_frac = est.fractional_kelly("real")
        sim_frac = est.fractional_kelly("sim")
        # SIM should always be >= REAL
        assert sim_frac >= real_frac

    def test_kelly_never_below_min_kelly(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        # All losses — raw Kelly would be very negative
        _feed_trades(est, wins=5, losses=45, avg_win=50.0, avg_loss=200.0)
        frac = est.fractional_kelly("real")
        assert frac >= 0.01, f"Kelly must not go below min_kelly=0.01, got {frac:.4f}"

    def test_record_fill_updates_window(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        est.record_fill({"pnl": 150.0})
        est.record_fill({"net_pnl": -50.0})
        assert len(list(est._trades)) == 2

    def test_snapshot_returns_correct_contract_type(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=20, losses=10)
        contract = est.snapshot("real")
        assert isinstance(contract, DynamicKellyContract)
        assert 0.0 <= contract.rolling_win_rate <= 1.0
        assert contract.window_trades == 30

    def test_log_estimate_creates_file(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=20, losses=10)
        est.log_estimate("real")
        history = tmp_path / "kelly_history.jsonl"
        assert history.exists()
        lines = history.read_text().strip().split("\n")
        assert len(lines) >= 1

    def test_rolling_window_max_size(self, tmp_path: Path):
        est = _make_estimator(tmp_path, window=10)
        for i in range(20):
            est.record_trade(float(i))
        # Only last 10 should be kept
        assert len(list(est._trades)) == 10

    def test_kelly_formula_correct_for_known_values(self, tmp_path: Path):
        """Verify classical Kelly formula: f* = (b·p - q) / b.

        With p=0.6, b=2 (avg_win=200, avg_loss=100):
        f* = (2·0.6 - 0.4) / 2 = (1.2 - 0.4) / 2 = 0.8 / 2 = 0.4
        Raw Kelly should be approximately 0.4.
        """
        est = _make_estimator(tmp_path, window=100)
        # 60 wins of 200, 40 losses of 100
        _feed_trades(est, wins=60, losses=40, avg_win=200.0, avg_loss=100.0)
        raw = est.raw_kelly()
        # Allow ±0.05 tolerance due to deque integer counts
        assert abs(raw - 0.4) < 0.05, f"Expected raw Kelly ≈ 0.4, got {raw:.3f}"


@pytest.mark.unit
class TestDynamicKellyContract:
    def test_profit_factor_calculation(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=30, losses=10, avg_win=300.0, avg_loss=100.0)
        contract = est.snapshot("sim")
        assert contract.rolling_profit_factor > 0.0

    def test_fractional_kelly_in_contract_le_cap(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=40, losses=10)
        contract = est.snapshot("real")
        assert contract.fractional_kelly <= 0.25


@pytest.mark.unit
class TestOrderBookReplay:
    def test_spread_ticks_positive(self):
        from lumina_core.backtester_engine import OrderBookReplay

        replay = OrderBookReplay()
        spread = replay.spread_ticks({"high": 5025.0, "low": 5020.0, "close": 5022.0}, atr=5.0)
        assert spread >= 1.0

    def test_spread_ticks_wider_at_open(self):
        from lumina_core.backtester_engine import OrderBookReplay

        replay = OrderBookReplay()
        bar = {"high": 5025.0, "low": 5020.0, "close": 5022.0}
        spread_open = replay.spread_ticks(bar, atr=5.0, time_period="open")
        spread_mid = replay.spread_ticks(bar, atr=5.0, time_period="midday")
        assert spread_open > spread_mid

    def test_market_impact_zero_for_zero_volume(self):
        from lumina_core.backtester_engine import OrderBookReplay

        replay = OrderBookReplay()
        impact = replay.market_impact_ticks(quantity=1.0, avg_volume=0.0)
        assert impact == 0.0

    def test_total_slippage_positive(self):
        from lumina_core.backtester_engine import OrderBookReplay

        replay = OrderBookReplay()
        bar = {"high": 5025.0, "low": 5020.0, "close": 5022.0}
        total = replay.total_slippage_ticks(bar, atr=5.0, quantity=1.0, avg_volume=1000.0)
        assert total > 0.0

    def test_market_impact_increases_with_quantity(self):
        from lumina_core.backtester_engine import OrderBookReplay

        replay = OrderBookReplay()
        impact_small = replay.market_impact_ticks(quantity=1.0, avg_volume=1000.0)
        impact_large = replay.market_impact_ticks(quantity=10.0, avg_volume=1000.0)
        assert impact_large > impact_small
