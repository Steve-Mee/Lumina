"""Tests for DynamicKellyEstimator — classical + volatility-adjusted Kelly.

All tests are unit-level: no I/O, no external services.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from lumina_core.risk.dynamic_kelly import DynamicKellyEstimator, _MIN_WINDOW_TRADES
from lumina_core.engine.financial_contracts import DynamicKellyContract


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_estimator(
    tmp_path: Path,
    window: int = 50,
    vol_scaling_enabled: bool = False,
    vol_target_annual: float = 0.15,
    vol_lookback_trades: int = 20,
) -> DynamicKellyEstimator:
    return DynamicKellyEstimator(
        window=window,
        min_kelly=0.01,
        fractional_kelly_real=0.25,
        fractional_kelly_sim=1.0,
        config_fallback_real=0.25,
        config_fallback_sim=1.0,
        vol_scaling_enabled=vol_scaling_enabled,
        vol_target_annual=vol_target_annual,
        vol_lookback_trades=vol_lookback_trades,
        history_path=tmp_path / "kelly_history.jsonl",
    )


def _feed_trades(
    estimator: DynamicKellyEstimator,
    wins: int,
    losses: int,
    avg_win: float = 200.0,
    avg_loss: float = 100.0,
) -> None:
    for _ in range(wins):
        estimator.record_trade(avg_win)
    for _ in range(losses):
        estimator.record_trade(-avg_loss)


# ---------------------------------------------------------------------------
# Classical Kelly tests (vol_scaling_enabled=False)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDynamicKellyEstimator:
    def test_fallback_before_sufficient_trades(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        for _ in range(_MIN_WINDOW_TRADES - 1):
            est.record_trade(100.0)
        assert est.fractional_kelly("real") == pytest.approx(0.25, rel=1e-3)

    def test_kelly_increases_with_good_winrate(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=35, losses=15, avg_win=200.0, avg_loss=100.0)
        raw = est.raw_kelly()
        assert raw > 0.3, f"Expected raw Kelly > 0.3 for high win-rate, got {raw:.3f}"

    def test_kelly_capped_in_real_mode(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=45, losses=5, avg_win=1000.0, avg_loss=50.0)
        frac = est.fractional_kelly("real")
        assert frac <= 0.25, f"REAL mode Kelly must not exceed 0.25, got {frac:.3f}"

    def test_kelly_allows_higher_in_sim(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
        _feed_trades(est, wins=40, losses=10, avg_win=300.0, avg_loss=100.0)
        real_frac = est.fractional_kelly("real")
        sim_frac = est.fractional_kelly("sim")
        assert sim_frac >= real_frac

    def test_kelly_never_below_min_kelly(self, tmp_path: Path):
        est = _make_estimator(tmp_path)
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

    def test_log_estimate_includes_vol_fields(self, tmp_path: Path):
        """Log must include vol_scaling_factor and vol_target_annual."""
        import json

        est = _make_estimator(tmp_path, vol_scaling_enabled=True)
        _feed_trades(est, wins=20, losses=10)
        est.log_estimate("real")
        record = json.loads((tmp_path / "kelly_history.jsonl").read_text().strip())
        assert "vol_scaling_factor" in record
        assert "vol_target_annual" in record

    def test_rolling_window_max_size(self, tmp_path: Path):
        est = _make_estimator(tmp_path, window=10)
        for i in range(20):
            est.record_trade(float(i))
        assert len(list(est._trades)) == 10

    def test_kelly_formula_correct_for_known_values(self, tmp_path: Path):
        """Verify f* = (b·p - q) / b.

        p=0.6, b=2 → f* = (2·0.6 - 0.4) / 2 = 0.4
        """
        est = _make_estimator(tmp_path, window=100)
        _feed_trades(est, wins=60, losses=40, avg_win=200.0, avg_loss=100.0)
        raw = est.raw_kelly()
        assert abs(raw - 0.4) < 0.05, f"Expected raw Kelly ≈ 0.4, got {raw:.3f}"


# ---------------------------------------------------------------------------
# Volatility-adjusted Kelly tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVolatilityAdjustedKelly:
    def test_vol_scalar_is_one_when_disabled(self, tmp_path: Path):
        est = _make_estimator(tmp_path, vol_scaling_enabled=False)
        _feed_trades(est, wins=30, losses=10, avg_win=1000.0, avg_loss=50.0)
        assert est.vol_scaling_factor() == pytest.approx(1.0)

    def test_vol_scalar_is_one_when_insufficient_data(self, tmp_path: Path):
        est = _make_estimator(tmp_path, vol_scaling_enabled=True, vol_lookback_trades=20)
        # Feed only 3 trades — below the 4-trade minimum threshold
        for _ in range(3):
            est.record_trade(100.0)
        assert est.vol_scaling_factor() == pytest.approx(1.0)

    def test_high_vol_reduces_kelly_fraction(self, tmp_path: Path):
        """High CV (large relative swings) should produce a lower vol scalar.

        The vol scaling uses CV = std / mean_abs_pnl, which is unit-invariant.

        - Low-CV:  uniform wins (~100) — tight distribution, CV ≈ 0.03
          → scalar ≈ 1.0 (target=0.10 > realized_cv → no cap)
        - High-CV: wild alternation of 100 and -90 — near-zero net, huge spread,
          CV ≈ 1.0 → scalar = min(1, 0.10/1.0) = 0.10
        """
        est_lowcv = _make_estimator(
            tmp_path / "lowcv", vol_scaling_enabled=True, vol_target_annual=0.10, vol_lookback_trades=20
        )
        est_highcv = _make_estimator(
            tmp_path / "highcv", vol_scaling_enabled=True, vol_target_annual=0.10, vol_lookback_trades=20
        )

        # Low-CV: tight wins around 100 (no losses) — std≈3, mean_abs≈100, CV≈0.03
        rng = random.Random(42)
        for _ in range(30):
            est_lowcv.record_trade(100.0 + rng.gauss(0, 3.0))

        # High-CV: wildly alternating +100 / -90 → std≈95, mean_abs≈95, CV≈1.0
        for i in range(30):
            est_highcv.record_trade(100.0 if i % 2 == 0 else -90.0)

        scalar_lowcv = est_lowcv.vol_scaling_factor()
        scalar_highcv = est_highcv.vol_scaling_factor()

        assert scalar_highcv < scalar_lowcv, (
            f"High-CV scalar ({scalar_highcv:.4f}) should be < low-CV scalar ({scalar_lowcv:.4f})"
        )
        # Low-CV should be close to 1.0 (target > realized CV)
        assert scalar_lowcv > 0.9, f"Low-CV scalar should be ~1.0, got {scalar_lowcv:.4f}"

    def test_low_vol_does_not_amplify_above_cap(self, tmp_path: Path):
        """Vol scaling must never push fraction above the fractional Kelly cap."""
        est = _make_estimator(tmp_path, vol_scaling_enabled=True, vol_target_annual=10.0)
        _feed_trades(est, wins=45, losses=5, avg_win=1.0, avg_loss=0.5)  # tiny, low-vol
        frac = est.fractional_kelly("real")
        assert frac <= 0.25, f"Vol scaling must not exceed cap (0.25), got {frac:.4f}"

    def test_vol_scalar_bounded_zero_to_one(self, tmp_path: Path):
        """Vol scalar must always be in [0, 1]."""
        est = _make_estimator(tmp_path, vol_scaling_enabled=True)
        for _ in range(50):
            est.record_trade(float(1e6))  # extreme values
        scalar = est.vol_scaling_factor()
        assert 0.0 <= scalar <= 1.0, f"Vol scalar out of bounds: {scalar}"

    def test_kelly_still_respects_min_kelly_with_vol_scaling(self, tmp_path: Path):
        """Even with aggressive vol scaling, floor is min_kelly."""
        est = _make_estimator(tmp_path, vol_scaling_enabled=True, vol_target_annual=0.001)
        _feed_trades(est, wins=30, losses=10, avg_win=500.0, avg_loss=50.0)
        frac = est.fractional_kelly("real")
        assert frac >= 0.01, f"min_kelly floor violated: {frac:.6f}"


# ---------------------------------------------------------------------------
# DynamicKellyContract tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# OrderBookReplay tests (cost model integration through backtester)
# ---------------------------------------------------------------------------


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
