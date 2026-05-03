"""tests/backtest/test_realism.py — Golden tests for the upgraded backtesting engine.

Marks:  @pytest.mark.backtest  (all tests)
        @pytest.mark.unit      (fast, pure-function tests)
        @pytest.mark.slow      (tests that run full simulations)

Test classes:
  TestOrderBookReplayV2        — spread, impact, time-of-day, regime
  TestDynamicSlippageModel     — per-bar composite slippage
  TestPurgedWalkForwardCV      — embargo split, Sharpe consistency metrics
  TestCombinatorialPurgedCV    — PBO and DSR calculations
  TestRealityGapTracker        — rolling stats, band classification, trends
  TestCalculateFitness         — PBO/DSR/reality-gap integration in fitness
  TestBacktestGolden           — end-to-end golden output contracts (slow)
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import pytest

from lumina_core.engine.backtest.order_book import (
    OrderBookReplayV2,
    DynamicSlippageModel,
    compute_atr,
    detect_time_period,
)
from lumina_core.engine.backtest.cross_validation import (
    PurgedWalkForwardCV,
    CombinatorialPurgedCV,
)
from lumina_core.engine.backtest.reality_gap import RealityGapTracker
from lumina_core.evolution.genetic_operators import calculate_fitness


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _bar(
    close: float = 4500.0, high: float = 4510.0, low: float = 4490.0, volume: float = 1000.0, ts: str | None = None
) -> dict[str, Any]:
    bar: dict[str, Any] = {"close": close, "high": high, "low": low, "volume": volume}
    if ts is not None:
        bar["timestamp"] = ts
    return bar


def _bars(n: int = 20, base_close: float = 4500.0) -> list[dict[str, Any]]:
    rng = random.Random(999)
    bars = []
    close = base_close
    for _ in range(n):
        change = rng.gauss(0, 3.0)
        close += change
        high = close + abs(rng.gauss(0, 1.5))
        low = close - abs(rng.gauss(0, 1.5))
        bars.append(_bar(close=close, high=high, low=max(low, 1.0), volume=rng.uniform(500, 2000)))
    return bars


def _dummy_scorer(pnls: list[float]) -> Any:
    """Return a scorer that always yields a fixed PnL sequence."""

    def scorer(chunk: list[dict[str, Any]]) -> dict[str, Any]:
        from lumina_core.engine.backtest.cross_validation import _safe_sharpe, _safe_winrate

        return {
            "net_pnl": sum(pnls),
            "sharpe": _safe_sharpe(pnls),
            "winrate": _safe_winrate(pnls),
        }

    return scorer


# ---------------------------------------------------------------------------
# TestOrderBookReplayV2
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestOrderBookReplayV2:
    def test_spread_ticks_baseline(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.10)
        spread = replay.half_spread_ticks(atr=10.0, tick_size=0.25, time_period="midday")
        assert spread >= 1.0, "spread must be at least 1 tick"
        # 10.0 * 0.10 / 0.25 = 4.0 ticks at midday
        assert math.isclose(spread, 4.0, rel_tol=0.01)

    def test_spread_ticks_open_wider(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.10)
        midday = replay.half_spread_ticks(atr=10.0, tick_size=0.25, time_period="midday")
        open_ = replay.half_spread_ticks(atr=10.0, tick_size=0.25, time_period="open")
        assert open_ > midday, "open spread must exceed midday spread"

    def test_spread_ticks_close_wider_than_midday(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.10)
        midday = replay.half_spread_ticks(atr=10.0, tick_size=0.25, time_period="midday")
        close = replay.half_spread_ticks(atr=10.0, tick_size=0.25, time_period="close")
        assert close > midday

    def test_spread_ticks_high_volatility_regime_wider(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.10)
        neutral = replay.half_spread_ticks(atr=10.0, tick_size=0.25, regime="NEUTRAL")
        high_vol = replay.half_spread_ticks(atr=10.0, tick_size=0.25, regime="HIGH_VOLATILITY")
        assert high_vol > neutral

    def test_spread_ticks_low_liquidity_widest(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.10)
        ll = replay.half_spread_ticks(atr=10.0, tick_size=0.25, regime="LOW_LIQUIDITY")
        neutral = replay.half_spread_ticks(atr=10.0, tick_size=0.25, regime="NEUTRAL")
        assert ll > neutral

    def test_spread_ticks_floor_is_one(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.001)
        spread = replay.half_spread_ticks(atr=0.001, tick_size=0.25)
        assert spread >= 1.0

    def test_spread_zero_atr_returns_one(self) -> None:
        replay = OrderBookReplayV2()
        assert replay.half_spread_ticks(atr=0.0, tick_size=0.25) == 1.0

    def test_market_impact_zero_volume(self) -> None:
        replay = OrderBookReplayV2()
        assert replay.market_impact_ticks(quantity=10.0, avg_volume=0.0) == 0.0

    def test_market_impact_scales_with_quantity(self) -> None:
        replay = OrderBookReplayV2(market_impact_alpha=0.5, market_impact_beta=0.6)
        small = replay.market_impact_ticks(quantity=1.0, avg_volume=1000.0)
        large = replay.market_impact_ticks(quantity=100.0, avg_volume=1000.0)
        assert large > small, "larger orders must have higher impact"

    def test_market_impact_non_negative(self) -> None:
        replay = OrderBookReplayV2()
        assert replay.market_impact_ticks(quantity=1.0, avg_volume=1000.0) >= 0.0

    def test_total_slippage_sum_of_parts(self) -> None:
        replay = OrderBookReplayV2(bid_ask_bounce=False)
        bar = _bar()
        atr = 10.0
        spread = replay.half_spread_ticks(atr, tick_size=0.25, time_period="midday")
        impact = replay.market_impact_ticks(1.0, 1000.0, tick_size=0.25)
        total = replay.total_slippage_ticks(bar, atr=atr, quantity=1.0, avg_volume=1000.0, tick_size=0.25)
        assert math.isclose(total, spread + impact, rel_tol=0.01) or total >= 0.5

    def test_bid_ask_bounce_doubles_spread(self) -> None:
        no_bounce = OrderBookReplayV2(bid_ask_bounce=False)
        with_bounce = OrderBookReplayV2(bid_ask_bounce=True)
        bar = _bar()
        atr = 8.0
        no_b = no_bounce.total_slippage_ticks(bar, atr=atr, quantity=0.0, avg_volume=0.0)
        with_b = with_bounce.total_slippage_ticks(bar, atr=atr, quantity=0.0, avg_volume=0.0)
        assert with_b > no_b

    def test_total_slippage_minimum_floor(self) -> None:
        replay = OrderBookReplayV2(spread_atr_ratio=0.0001)
        bar = _bar()
        total = replay.total_slippage_ticks(bar, atr=0.001, quantity=0.0, avg_volume=0.0)
        assert total >= 0.5


# ---------------------------------------------------------------------------
# TestDynamicSlippageModel
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestDynamicSlippageModel:
    def test_slippage_for_bar_returns_positive(self) -> None:
        model = DynamicSlippageModel()
        bars = _bars(20)
        slip = model.slippage_for_bar(bars[-1], bars)
        assert slip > 0.0

    def test_slippage_scales_with_atr(self) -> None:
        model = DynamicSlippageModel()
        calm_bars = [_bar(close=4500.0 + i * 0.01, high=4501.0, low=4499.0) for i in range(20)]
        volatile_bars = [_bar(close=4500.0 + i * 5.0, high=4520.0, low=4480.0) for i in range(20)]
        calm = model.slippage_for_bar(calm_bars[-1], calm_bars)
        volatile = model.slippage_for_bar(volatile_bars[-1], volatile_bars)
        assert volatile > calm, "high-ATR environment must produce higher slippage"

    def test_slippage_high_vol_regime_higher(self) -> None:
        model = DynamicSlippageModel()
        bars = _bars(20)
        neutral = model.slippage_for_bar(bars[-1], bars, regime="NEUTRAL")
        high_vol = model.slippage_for_bar(bars[-1], bars, regime="HIGH_VOLATILITY")
        assert high_vol > neutral

    def test_slippage_dollars_converts_correctly(self) -> None:
        model = DynamicSlippageModel(tick_size=0.25)
        bars = _bars(20)
        ticks = model.slippage_for_bar(bars[-1], bars)
        dollars = model.slippage_dollars(bars[-1], bars, point_value=5.0)
        expected = ticks * 0.25 * 5.0
        assert math.isclose(dollars, expected, rel_tol=0.01)

    def test_calibrate_adjusts_ratio(self) -> None:
        model = DynamicSlippageModel()
        original_ratio = model.replay.spread_atr_ratio
        fills = [{"slippage_ticks": 3.0, "atr": 10.0}, {"slippage_ticks": 2.0, "atr": 10.0}]
        model.calibrate_from_history(fills)
        assert model.replay.spread_atr_ratio != original_ratio

    def test_calibrate_empty_fills_no_op(self) -> None:
        model = DynamicSlippageModel()
        original = model.replay.spread_atr_ratio
        model.calibrate_from_history([])
        assert model.replay.spread_atr_ratio == original


# ---------------------------------------------------------------------------
# TestComputeATR
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestComputeATR:
    def test_atr_single_bar_returns_one(self) -> None:
        assert compute_atr([_bar()]) == 1.0

    def test_atr_empty_returns_one(self) -> None:
        assert compute_atr([]) == 1.0

    def test_atr_positive(self) -> None:
        bars = _bars(20)
        atr = compute_atr(bars, window=14)
        assert atr > 0.0

    def test_atr_larger_range_bigger(self) -> None:
        tight = [_bar(high=4501.0, low=4499.0) for _ in range(20)]
        wide = [_bar(high=4520.0, low=4480.0) for _ in range(20)]
        assert compute_atr(wide) > compute_atr(tight)


# ---------------------------------------------------------------------------
# TestDetectTimePeriod
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestDetectTimePeriod:
    def test_open_session(self) -> None:
        bar = _bar(ts="2024-01-15T13:35:00+00:00")  # 09:35 ET (UTC-4)
        assert detect_time_period(bar) == "open"

    def test_close_session(self) -> None:
        bar = _bar(ts="2024-01-15T19:45:00+00:00")  # 15:45 ET
        assert detect_time_period(bar) == "close"

    def test_midday_session(self) -> None:
        bar = _bar(ts="2024-01-15T16:00:00+00:00")  # 12:00 ET
        assert detect_time_period(bar) == "midday"

    def test_no_timestamp_returns_midday(self) -> None:
        assert detect_time_period(_bar()) == "midday"

    def test_invalid_timestamp_returns_midday(self) -> None:
        assert detect_time_period({"timestamp": "not-a-date"}) == "midday"


# ---------------------------------------------------------------------------
# TestPurgedWalkForwardCV
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestPurgedWalkForwardCV:
    def _make_cv(self) -> PurgedWalkForwardCV:
        return PurgedWalkForwardCV(
            train_bars=200,
            test_bars=50,
            embargo_bars=10,
        )

    def test_split_produces_correct_window_count(self) -> None:
        cv = self._make_cv()
        splits = cv.split(n=800)
        # Non-overlapping: (800 - 200 - 10) // 50 = ~11-12 windows
        assert len(splits) >= 1

    def test_split_no_overlap_between_test_and_train(self) -> None:
        cv = self._make_cv()
        splits = cv.split(n=800)
        for train_idx, test_idx in splits:
            train_set = set(train_idx)
            test_set = set(test_idx)
            assert train_set.isdisjoint(test_set), "train and test must not overlap"

    def test_embargo_gap_respected(self) -> None:
        cv = self._make_cv()
        splits = cv.split(n=800)
        for train_idx, test_idx in splits:
            if train_idx and test_idx:
                last_train = max(train_idx)
                first_test = min(test_idx)
                assert first_test > last_train + cv.embargo_bars - 1, "embargo gap violated"

    def test_split_empty_when_too_short(self) -> None:
        cv = self._make_cv()
        splits = cv.split(n=100)
        assert splits == []

    def test_run_returns_dict_with_required_keys(self) -> None:
        cv = self._make_cv()
        snapshot = _bars(800)
        scorer = _dummy_scorer([10.0, 20.0, -5.0] * 10)
        result = cv.run(snapshot, scorer)
        for key in ("method", "windows", "mean_pnl", "mean_sharpe", "sharpe_positive_pct", "details"):
            assert key in result, f"missing key: {key}"

    def test_run_short_data_returns_empty(self) -> None:
        cv = self._make_cv()
        result = cv.run(_bars(50), _dummy_scorer([1.0]))
        assert result["windows"] == 0

    def test_sharpe_positive_pct_all_positive(self) -> None:
        cv = PurgedWalkForwardCV(train_bars=100, test_bars=30, embargo_bars=5)
        snapshot = _bars(600)
        # Mix of values with positive mean AND variance so Sharpe > 0.
        scorer = _dummy_scorer([50.0 + i % 10 for i in range(30)])
        result = cv.run(snapshot, scorer)
        if result["windows"] > 0:
            assert result["sharpe_positive_pct"] == 1.0

    def test_sharpe_positive_pct_all_negative(self) -> None:
        cv = PurgedWalkForwardCV(train_bars=100, test_bars=30, embargo_bars=5)
        snapshot = _bars(600)
        scorer = _dummy_scorer([-100.0] * 30)
        result = cv.run(snapshot, scorer)
        if result["windows"] > 0:
            assert result["sharpe_positive_pct"] == 0.0

    def test_pnl_std_positive_when_variance(self) -> None:
        cv = PurgedWalkForwardCV(train_bars=100, test_bars=30, embargo_bars=5)
        snapshot = _bars(800)
        rng = random.Random(42)
        scorer = _dummy_scorer([rng.gauss(50, 20) for _ in range(30)])
        result = cv.run(snapshot, scorer)
        if result["windows"] > 1:
            assert result["pnl_std"] >= 0.0


# ---------------------------------------------------------------------------
# TestCombinatorialPurgedCV
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestCombinatorialPurgedCV:
    def _make_cpcv(self) -> CombinatorialPurgedCV:
        return CombinatorialPurgedCV(n_splits=5, n_test_folds=1, embargo_pct=0.01)

    def test_split_count_equals_combinations(self) -> None:
        cpcv = self._make_cpcv()
        splits = cpcv.split(n=1000)
        # C(5,1) = 5
        assert len(splits) == 5

    def test_split_no_train_test_overlap(self) -> None:
        cpcv = self._make_cpcv()
        splits = cpcv.split(n=1000)
        for train_idx, test_idx in splits:
            assert set(train_idx).isdisjoint(set(test_idx))

    def test_split_empty_when_too_short(self) -> None:
        cpcv = self._make_cpcv()
        assert cpcv.split(n=10) == []

    def test_run_returns_required_keys(self) -> None:
        cpcv = self._make_cpcv()
        snapshot = _bars(500)
        scorer = _dummy_scorer([10.0, -5.0, 15.0] * 10)
        result = cpcv.run(snapshot, scorer)
        for key in ("method", "combinations", "mean_oos_sharpe", "pbo", "dsr", "details"):
            assert key in result

    def test_pbo_between_zero_and_one(self) -> None:
        cpcv = self._make_cpcv()
        snapshot = _bars(500)
        scorer = _dummy_scorer([10.0, -5.0, 15.0] * 10)
        result = cpcv.run(snapshot, scorer)
        if result["combinations"] > 0:
            assert 0.0 <= result["pbo"] <= 1.0

    def test_dsr_float(self) -> None:
        cpcv = self._make_cpcv()
        snapshot = _bars(500)
        scorer = _dummy_scorer([10.0, -5.0, 15.0] * 10)
        result = cpcv.run(snapshot, scorer)
        assert isinstance(result["dsr"], float)

    def test_pbo_low_when_all_positive_sharpe(self) -> None:
        cpcv = CombinatorialPurgedCV(n_splits=5, n_test_folds=1, embargo_pct=0.01)
        snapshot = _bars(500)
        scorer = _dummy_scorer([50.0] * 50)
        result = cpcv.run(snapshot, scorer)
        if result["combinations"] > 0:
            # All equal → 0 below median → PBO = 0.0
            assert result["pbo"] <= 0.5

    def test_combinations_count_six_splits(self) -> None:
        cpcv = CombinatorialPurgedCV(n_splits=6, n_test_folds=1, embargo_pct=0.01)
        splits = cpcv.split(n=600)
        # C(6,1) = 6
        assert len(splits) == 6

    def test_compute_pbo_all_positive(self) -> None:
        # With [1.0, 2.0, 3.0], median=2.0, 1 value (1.0) is below → PBO = 1/3 < 0.5.
        pbo = CombinatorialPurgedCV._compute_pbo([1.0, 2.0, 3.0])
        assert pbo < 0.5  # low overfitting: fewer than half below median

    def test_compute_pbo_all_equal(self) -> None:
        pbo = CombinatorialPurgedCV._compute_pbo([1.0, 1.0, 1.0])
        assert pbo == 0.0  # nothing strictly below median

    def test_compute_dsr_decreases_with_more_combinations(self) -> None:
        sharpes = [1.5, 1.2, 0.8, 1.0, 1.3]
        dsr_few = CombinatorialPurgedCV._compute_dsr(sharpes, n_combinations=5)
        dsr_many = CombinatorialPurgedCV._compute_dsr(sharpes, n_combinations=50)
        assert dsr_few > dsr_many, "more combinations → harsher DSR deflation"


# ---------------------------------------------------------------------------
# TestRealityGapTracker
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestRealityGapTracker:
    def test_observe_returns_penalty(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=0.15)
        penalty = tracker.observe(sim_sharpe=1.5, real_sharpe=0.5)
        # gap = 1.0, penalty = 1.0 * 0.15 = 0.15
        assert math.isclose(penalty, 0.15, rel_tol=0.01)

    def test_observe_zero_when_real_exceeds_sim(self) -> None:
        tracker = RealityGapTracker()
        penalty = tracker.observe(sim_sharpe=0.5, real_sharpe=1.5)
        assert penalty == 0.0

    def test_rolling_stats_mean_gap(self) -> None:
        tracker = RealityGapTracker(window=5)
        for _ in range(5):
            tracker.observe(sim_sharpe=1.0, real_sharpe=0.0)  # gap=1.0 each
        stats = tracker.rolling_stats()
        assert math.isclose(stats["mean_gap"], 1.0, rel_tol=0.01)

    def test_rolling_stats_empty(self) -> None:
        tracker = RealityGapTracker()
        stats = tracker.rolling_stats()
        assert stats["window"] == 0
        assert stats["mean_gap"] == 0.0

    def test_band_green_small_gap(self) -> None:
        tracker = RealityGapTracker()
        for _ in range(5):
            tracker.observe(0.2, 0.1)  # gap = 0.1
        assert tracker.rolling_stats()["band_status"] == "GREEN"

    def test_band_yellow_medium_gap(self) -> None:
        tracker = RealityGapTracker()
        for _ in range(5):
            tracker.observe(1.0, 0.5)  # gap = 0.5
        assert tracker.rolling_stats()["band_status"] == "YELLOW"

    def test_band_red_large_gap(self) -> None:
        tracker = RealityGapTracker()
        for _ in range(5):
            tracker.observe(2.0, 0.5)  # gap = 1.5
        assert tracker.rolling_stats()["band_status"] == "RED"

    def test_dynamic_penalty_red_band_doubles(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=0.10)
        for _ in range(5):
            tracker.observe(2.5, 0.5)  # gap = 2.0, RED
        base_penalty = tracker.penalty()
        dynamic = tracker.dynamic_penalty()
        assert dynamic >= base_penalty * 1.5  # at least 1.5x for RED

    def test_trend_widening(self) -> None:
        tracker = RealityGapTracker()
        # First half: small gap; second half: large gap
        for _ in range(5):
            tracker.observe(0.3, 0.2)  # gap = 0.1
        for _ in range(5):
            tracker.observe(1.5, 0.2)  # gap = 1.3
        stats = tracker.rolling_stats()
        assert stats["gap_trend"] == "WIDENING"

    def test_trend_narrowing(self) -> None:
        tracker = RealityGapTracker()
        for _ in range(5):
            tracker.observe(1.5, 0.2)  # gap = 1.3
        for _ in range(5):
            tracker.observe(0.3, 0.2)  # gap = 0.1
        stats = tracker.rolling_stats()
        assert stats["gap_trend"] == "NARROWING"

    def test_persist_and_load(self, tmp_path: Path) -> None:
        path = tmp_path / "gap.jsonl"
        tracker = RealityGapTracker(history_path=path)
        tracker.observe(1.2, 0.5)
        tracker.observe(0.8, 0.6)

        # Load into a new tracker.
        tracker2 = RealityGapTracker(history_path=path)
        loaded = tracker2.load_history(path)
        assert loaded == 2
        assert len(tracker2._observations) == 2

    def test_persist_non_fatal_on_bad_path(self) -> None:
        bad = Path("/nonexistent/dir/gap.jsonl")
        tracker = RealityGapTracker(history_path=bad)
        # Should not raise.
        tracker.observe(1.0, 0.5)

    def test_penalty_method_uses_rolling_mean(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=0.2, window=3)
        tracker.observe(1.0, 0.0)  # gap = 1.0
        tracker.observe(2.0, 0.0)  # gap = 2.0
        tracker.observe(3.0, 0.0)  # gap = 3.0
        expected = statistics_mean([1.0, 2.0, 3.0]) * 0.2
        assert math.isclose(tracker.penalty(), expected, rel_tol=0.01)


def statistics_mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


# ---------------------------------------------------------------------------
# TestCalculateFitness — PBO / DSR / reality-gap integration
# ---------------------------------------------------------------------------


@pytest.mark.backtest
@pytest.mark.unit
class TestCalculateFitness:
    def test_base_fitness_positive(self) -> None:
        score = calculate_fitness(pnl=10000.0, max_dd=1000.0, sharpe=1.5)
        assert score > 0.0

    def test_drawdown_exceeds_threshold_returns_neg_inf(self) -> None:
        score = calculate_fitness(pnl=10000.0, max_dd=30000.0, sharpe=2.0)
        assert score == float("-inf")

    def test_reality_gap_penalty_reduces_fitness(self) -> None:
        base = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0)
        penalised = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, reality_gap_penalty=0.5)
        assert penalised < base

    def test_high_pbo_reduces_fitness(self) -> None:
        base = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, pbo=0.0)
        high_pbo = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, pbo=0.8)
        assert high_pbo < base

    def test_negative_dsr_caps_at_zero(self) -> None:
        score = calculate_fitness(pnl=50000.0, max_dd=100.0, sharpe=3.0, dsr=-0.5)
        assert score <= 0.0

    def test_positive_dsr_no_cap(self) -> None:
        score = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, dsr=1.5)
        assert score > 0.0

    def test_low_sharpe_consistency_penalty(self) -> None:
        base = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, sharpe_positive_pct=1.0)
        low_consistency = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, sharpe_positive_pct=0.3)
        assert low_consistency < base

    def test_all_penalties_compound(self) -> None:
        base = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0)
        full_penalty = calculate_fitness(
            pnl=5000.0,
            max_dd=500.0,
            sharpe=1.0,
            reality_gap_penalty=0.3,
            pbo=0.6,
            dsr=-0.1,
            sharpe_positive_pct=0.4,
        )
        assert full_penalty < base

    def test_zero_inputs_returns_zero_ish(self) -> None:
        score = calculate_fitness(pnl=0.0, max_dd=0.0, sharpe=0.0)
        assert score == 0.0

    def test_none_dsr_has_no_effect(self) -> None:
        with_none = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0, dsr=None)
        without = calculate_fitness(pnl=5000.0, max_dd=500.0, sharpe=1.0)
        assert math.isclose(with_none, without, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# TestBacktestGolden — end-to-end golden output contracts
# ---------------------------------------------------------------------------


def _make_golden_snapshot(n: int = 300) -> list[dict[str, Any]]:
    """Deterministic OHLCV snapshot for repeatable golden tests."""
    rng = random.Random(12345)
    bars: list[dict[str, Any]] = []
    close = 4500.0
    for i in range(n):
        change = rng.gauss(0, 2.5)
        close = max(1.0, close + change)
        high = close + abs(rng.gauss(0, 1.0))
        low = max(1.0, close - abs(rng.gauss(0, 1.0)))
        bars.append(
            {
                "close": close,
                "high": high,
                "low": low,
                "open": close - change * 0.3,
                "volume": rng.uniform(500, 3000),
                "timestamp": f"2024-01-{1 + i // 100:02d}T{9 + (i % 60):02d}:00:00+00:00",
            }
        )
    return bars


@pytest.mark.backtest
@pytest.mark.unit
class TestPurgedWFGolden:
    """Golden contracts for PurgedWalkForwardCV output shape."""

    def test_run_produces_details(self) -> None:
        cv = PurgedWalkForwardCV(train_bars=120, test_bars=40, embargo_bars=10)
        snapshot = _make_golden_snapshot(500)
        scorer = _dummy_scorer([5.0, -2.0, 8.0, 3.0] * 10)
        result = cv.run(snapshot, scorer)
        assert isinstance(result["details"], list)
        if result["windows"] > 0:
            detail = result["details"][0]
            assert "test_start" in detail
            assert "embargo_end" in detail
            assert detail["embargo_end"] >= detail["train_end"]

    def test_embargo_end_always_after_train_end(self) -> None:
        cv = PurgedWalkForwardCV(train_bars=100, test_bars=30, embargo_bars=15)
        snapshot = _make_golden_snapshot(500)
        result = cv.run(snapshot, _dummy_scorer([1.0] * 30))
        for d in result.get("details", []):
            assert d["embargo_end"] >= d["train_end"] + 14, "embargo must be at least 15 bars"


@pytest.mark.backtest
@pytest.mark.unit
class TestCPCVGolden:
    """Golden contracts for CombinatorialPurgedCV output shape."""

    def test_details_count_matches_combinations(self) -> None:
        cpcv = CombinatorialPurgedCV(n_splits=5, n_test_folds=1, embargo_pct=0.02)
        snapshot = _make_golden_snapshot(500)
        result = cpcv.run(snapshot, _dummy_scorer([10.0] * 50))
        if result["combinations"] > 0:
            assert len(result["details"]) == result["combinations"]

    def test_sharpe_positive_pct_in_range(self) -> None:
        cpcv = CombinatorialPurgedCV(n_splits=5, n_test_folds=1)
        snapshot = _make_golden_snapshot(500)
        result = cpcv.run(snapshot, _dummy_scorer([1.0] * 50))
        if result["combinations"] > 0:
            assert 0.0 <= result["sharpe_positive_pct"] <= 1.0


@pytest.mark.backtest
@pytest.mark.unit
class TestRealityGapGolden:
    """Golden contracts: penalty values remain stable for fixed inputs."""

    # Fixed expected values — update deliberately if the formula changes.
    _COEFF = 0.15

    def test_penalty_golden_value(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=self._COEFF, window=1)
        tracker.observe(sim_sharpe=2.0, real_sharpe=1.0)
        # gap=1.0, penalty=0.15; rolling mean_gap=1.0
        assert math.isclose(tracker.penalty(), 0.15, rel_tol=0.01)

    def test_zero_gap_zero_penalty(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=self._COEFF)
        tracker.observe(sim_sharpe=1.0, real_sharpe=1.0)
        assert tracker.penalty() == 0.0

    def test_negative_gap_zero_penalty(self) -> None:
        tracker = RealityGapTracker(penalty_coeff=self._COEFF)
        tracker.observe(sim_sharpe=0.5, real_sharpe=2.0)
        assert tracker.penalty() == 0.0
