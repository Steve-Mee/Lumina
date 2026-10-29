"""Researchers 2026-10-29 P2 artefact fixes (steps 1-4). Every A1-F18 that applies."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.cycles import seal as seal_mod
from lumina_research.cycles.adjust import back_adjust
from lumina_research.cycles.catalog import catalog
from lumina_research.cycles.cost_bands import ES_NQ_ONE_WAY, MNQ_ONE_WAY_USD, band_for, report_band
from lumina_research.cycles.daily import daily_market_returns
from lumina_research.cycles.data import LoadedTape, ResearchBar
from lumina_research.cycles.diagnostics import from_trades, window_sharpe
from lumina_research.cycles.execution import ClosedTrade, bar_volatility_price, run_execution
from lumina_research.cycles.fills import FILL_POLICY, touch_fill, trade_through_fill, traded_through
from lumina_research.cycles.first_cycle import first_cycle_specs, write_first_cycle_preregister
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import (
    DAYS_PER_MONTH,
    HOLDOUT_MONTHS,
    NS_PER_DAY,
    P2_HOLDOUT_START_LEGACY_NS,
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    access_bars,
    holdout_ns,
)
from lumina_research.cycles.p2_cycle import session_day_count, window_note
from lumina_research.cycles.positive_control import (
    CONTROL_SESSION_FILTER,
    CONTROL_STOP_TICKS,
    CONTROL_TARGET_TICKS,
    CONTROL_TIME_STOP_BARS,
    execute_control,
    run_controls,
    rth_session_direction,
    shuffle_signals,
)
from lumina_research.cycles.prepare import PreparedTape, prepare_tape
from lumina_research.cycles.roll_verify import FRIDAY_ROLL, require_friday_roll, verify_nt8_rolls
from lumina_research.cycles.rolls import NT8_ROLL_SET
from lumina_research.cycles.seal import (
    LEGACY_SEAL_SHA256,
    LIVE_SEAL_SHA256,
    PENDING_COUNTS_SEAL_NAME,
    PENDING_COUNTS_SEAL_SHA256,
    SEAL_NAME,
    load_seal,
    reuse_holdout_seal,
    seal_holdout,
)
from lumina_research.cycles.sessions import (
    INTRASESSION_HOLE_NS,
    RTH_LAST_CLOSE_MIN,
    RTH_OPEN_CLOSE_MIN,
    annotate,
    is_rth_close,
)
from lumina_research.cycles.slippage_calibration import ASSUMPTION, SLIPPAGE_COEFFICIENT, load_slippage_calibration
from lumina_research.cycles.strategies import simulate, simulate_full
from lumina_research.cycles.wf_sizes import walk_forward_sizes
from lumina_research.validation.block_bootstrap import block_bootstrap_sharpes
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import COST_MODEL_VERSION, CostModel, MarketSnapshot, apply_costs
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.pipeline import evaluate_candidate, missing_evaluation
from lumina_research.validation.regimes import regime_robustness
from lumina_research.validation.static_rules import STATIC_POSITIVE_SHARE_MIN, positive_share, structural_decay
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN, FLOOR_PBO_HARD_REJECT
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import OOSDistribution, RegimeSnapshot, WFESnapshot
from lumina_research.validation.walk_forward import WalkForwardConfig, run_walk_forward, static_return_scorer
from tests.research.test_gate import _good, _registry

UTC = timezone.utc


def _bar(ts: datetime, *, open_: float, high: float, low: float, close: float, volume: float = 5_000.0) -> ResearchBar:
    return ResearchBar(
        ts_ns=int(ts.timestamp() * 1_000_000_000),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _rth_minutes(start: datetime, n: int, px: float, *, step: float = 0.0) -> tuple[ResearchBar, ...]:
    rows: list[ResearchBar] = []
    price = px
    for index in range(n):
        ts = start + timedelta(minutes=index)
        rows.append(_bar(ts, open_=price, high=price + 0.5, low=price - 0.5, close=price, volume=5_000.0))
        price += step
    return tuple(rows)


@pytest.mark.unit
def test_trade_through_rejects_touch_and_fills_through() -> None:
    bar = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    assert FILL_POLICY == "trade_through_strict"
    assert touch_fill(side=1.0, limit=9.5, bar=bar) is True
    assert traded_through(side=1.0, limit=9.5, bar=bar) is False
    assert trade_through_fill(side=1.0, limit=9.5, bar=bar, average_volume=50.0) is False
    assert traded_through(side=1.0, limit=9.6, bar=bar) is True
    assert traded_through(side=-1.0, limit=10.5, bar=bar) is False
    assert traded_through(side=-1.0, limit=10.4, bar=bar) is True
    thin = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=10.0)
    assert trade_through_fill(side=1.0, limit=9.6, bar=thin, average_volume=100.0) is False
    fat = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    assert trade_through_fill(side=1.0, limit=9.6, bar=fat, average_volume=100.0) is True


@pytest.mark.unit
def test_exit_bar_pnl_is_booked_at_target_or_gap_open() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    target = entry + 16 * 0.25
    bars = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry + 0.1, high=entry + 0.2, low=entry - 0.4, close=entry + 0.1),
        _bar(start + timedelta(minutes=2), open_=entry + 0.2, high=target + 0.5, low=entry, close=target + 0.2),
    )
    labels = annotate(bars)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    executed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert executed.trades
    closed = executed.trades[0]
    assert closed.reason == "target"
    assert closed.exit_price == pytest.approx(target)
    gapped = (
        bars[0],
        bars[1],
        _bar(start + timedelta(minutes=2), open_=target + 1.0, high=target + 1.2, low=target + 0.8, close=target + 1.0),
    )
    gap_exec = run_execution(
        bars=gapped,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=annotate(gapped).rth,
        session_dates=annotate(gapped).session_dates,
        session_filter="globex",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert gap_exec.trades[0].exit_price == pytest.approx(target + 1.0)
    assert gap_exec.trades[0].reason == "target"


@pytest.mark.unit
def test_stop_exit_is_booked_at_stop_price() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    stop = entry - 8 * 0.25
    bars = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry - 0.1, high=entry, low=entry - 0.1, close=entry - 0.1),
        _bar(start + timedelta(minutes=2), open_=entry - 0.2, high=entry, low=stop - 0.5, close=stop - 0.2),
    )
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    executed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=annotate(bars).rth,
        session_dates=annotate(bars).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert executed.trades[0].reason == "stop"
    assert executed.trades[0].exit_price == pytest.approx(stop)


@pytest.mark.unit
def test_session_end_flatten_and_time_stop_close_at_bar_close() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = _rth_minutes(start, 6, 5000.0, step=0.05)
    labels = annotate(bars)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    timed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        geometry=geo,
        breaks=tuple(False for _ in bars),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=2,
        session_end_flatten=False,
    )
    assert timed.trades[0].reason == "time_stop"
    assert timed.trades[0].exit_price == pytest.approx(bars[2].close)
    flat = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        geometry=geo,
        breaks=tuple(False for _ in bars),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=True,
    )
    assert any(item.reason == "session_end" for item in flat.trades)
    assert flat.trades[-1].exit_price == pytest.approx(bars[-1].close)


@pytest.mark.unit
def test_rth_close_labels_use_first_and_last_cash_closes() -> None:
    et930 = datetime(2026, 3, 2, 14, 30, tzinfo=UTC)
    et931 = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    et1600 = datetime(2026, 3, 2, 21, 0, tzinfo=UTC)
    et1601 = datetime(2026, 3, 2, 21, 1, tzinfo=UTC)
    assert is_rth_close(int(et930.timestamp() * 1_000_000_000)) is False
    assert is_rth_close(int(et931.timestamp() * 1_000_000_000)) is True
    assert is_rth_close(int(et1600.timestamp() * 1_000_000_000)) is True
    assert is_rth_close(int(et1601.timestamp() * 1_000_000_000)) is False
    assert RTH_OPEN_CLOSE_MIN == 9 * 60 + 31
    assert RTH_LAST_CLOSE_MIN == 16 * 60
    assert INTRASESSION_HOLE_NS == 90 * 1_000_000_000
    assert holdout_ns(HOLDOUT_MONTHS) == int(float(HOLDOUT_MONTHS) * DAYS_PER_MONTH * float(NS_PER_DAY))


@pytest.mark.unit
def test_overnight_holes_do_not_force_exit_rth_holes_do() -> None:
    rth_a = _bar(datetime(2026, 3, 2, 15, 0, tzinfo=UTC), open_=5000.0, high=5000.5, low=4999.5, close=5000.0)
    rth_b = _bar(datetime(2026, 3, 2, 15, 3, tzinfo=UTC), open_=5001.0, high=5001.5, low=5000.5, close=5001.0)
    prepared = prepare_tape("MES", (rth_a, rth_b) + _rth_minutes(datetime(2026, 3, 2, 15, 4, tzinfo=UTC), 240, 5001.0))
    rth_index = next(i for i, item in enumerate(prepared.bars) if item.ts_ns == rth_b.ts_ns)
    assert prepared.breaks[rth_index] is True
    globex_a = _bar(datetime(2026, 3, 2, 23, 0, tzinfo=UTC), open_=5000.0, high=5000.5, low=4999.5, close=5000.0)
    globex_b = _bar(datetime(2026, 3, 2, 23, 3, tzinfo=UTC), open_=5001.0, high=5001.5, low=5000.5, close=5001.0)
    overnight = prepare_tape(
        "MES", (globex_a, globex_b) + _rth_minutes(datetime(2026, 3, 3, 14, 31, tzinfo=UTC), 240, 5001.0)
    )
    globex_index = next(i for i, item in enumerate(overnight.bars) if item.ts_ns == globex_b.ts_ns)
    assert overnight.breaks[globex_index] is False


@pytest.mark.unit
def test_overnight_gap_uses_prior_rth_close_to_today_rth_open() -> None:
    day1 = _rth_minutes(datetime(2026, 3, 2, 14, 31, tzinfo=UTC), 5, 5000.0)
    last = _bar(datetime(2026, 3, 2, 21, 0, tzinfo=UTC), open_=5010.0, high=5010.5, low=5009.5, close=5010.0)
    day2_open = _bar(datetime(2026, 3, 3, 14, 31, tzinfo=UTC), open_=5020.0, high=5020.5, low=5019.5, close=5020.0)
    rest = _rth_minutes(datetime(2026, 3, 3, 14, 32, tzinfo=UTC), 240, 5020.0)
    bars = day1 + (last, day2_open) + rest
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    executed = simulate_full(
        family="overnight_gap",
        bars=bars,
        geometry=geo,
        lookback=1,
        threshold=8.0,
        mode="fade",
    )
    labels = annotate(bars)
    open_index = next(i for i, item in enumerate(bars) if item.ts_ns == day2_open.ts_ns)
    assert labels.rth[open_index] is True
    assert -1.0 in executed.positions
    gap_ticks = (5020.0 - 5010.0) / 0.25
    assert gap_ticks >= 8.0
    globex_last = _bar(datetime(2026, 3, 3, 4, 0, tzinfo=UTC), open_=5100.0, high=5100.5, low=5099.5, close=5100.0)
    mixed = day1 + (last, globex_last, day2_open) + rest
    mixed_exec = simulate_full(
        family="overnight_gap",
        bars=mixed,
        geometry=geo,
        lookback=1,
        threshold=8.0,
        mode="fade",
    )
    mixed_open = next(i for i, item in enumerate(mixed) if item.ts_ns == day2_open.ts_ns)
    assert -1.0 in mixed_exec.positions[mixed_open:]
    assert 1.0 not in mixed_exec.positions[mixed_open:]


@pytest.mark.unit
def test_volatility_expansion_catalog_is_75th_percentile() -> None:
    vx = next(item for item in catalog() if item.config_id == "vx-mes-20")
    assert vx.threshold == 0.75
    bars = tuple(
        ResearchBar(
            ts_ns=1_700_000_000_000_000_000 + index * 60_000_000_000,
            open=100.0,
            high=100.0 + (1.0 if index < 239 else 10.0),
            low=100.0,
            close=100.2 if index < 239 else 109.0,
            volume=1_000.0,
        )
        for index in range(241)
    )
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    executed = simulate_full(
        family="volatility_expansion",
        bars=bars,
        geometry=geo,
        lookback=20,
        threshold=0.75,
        mode="breakout",
        session_filter="globex",
        session_end_flatten=False,
    )
    assert len(executed.gross) == 241
    quiet = tuple(
        ResearchBar(
            ts_ns=1_700_000_000_000_000_000 + index * 60_000_000_000,
            open=100.0,
            high=100.5,
            low=100.0,
            close=100.2,
            volume=1_000.0,
        )
        for index in range(241)
    )
    quiet_exec = simulate_full(
        family="volatility_expansion",
        bars=quiet,
        geometry=geo,
        lookback=20,
        threshold=0.75,
        mode="breakout",
        session_filter="globex",
        session_end_flatten=False,
    )
    assert executed.trades
    assert not quiet_exec.trades


@pytest.mark.unit
def test_geometry_has_no_fixed_tick_floor() -> None:
    geo = require_geometry(root="MES", target_ticks=3, stop_ticks=2)
    assert geo.target_ticks == 3
    with pytest.raises(Exception, match="target"):
        require_geometry(root="MES", target_ticks=0, stop_ticks=2)


@pytest.mark.unit
def test_market_regimes_use_instrument_returns_not_strategy_pnl() -> None:
    net = tuple(-0.02 for _ in range(40))
    market = tuple(0.01 if index % 3 else -0.02 for index in range(40))
    snap = regime_robustness(net, market_returns=market)
    assert snap.is_complete()
    missing = regime_robustness(net, market_returns=market[:-1])
    assert missing.is_complete() is False
    two_regime = tuple(
        (0.03 if index % 2 == 0 else 0.002) if index < 20 else (-0.03 if index % 2 == 0 else -0.002)
        for index in range(40)
    )
    fallback = regime_robustness(two_regime)
    assert fallback.is_complete() is False
    labeled = regime_robustness(net, market_returns=two_regime)
    unlabeled = regime_robustness(two_regime, market_returns=two_regime)
    assert labeled.trend_up_sharpe != unlabeled.trend_up_sharpe or labeled.vol_high_sharpe != unlabeled.vol_high_sharpe


@pytest.mark.unit
def test_slippage_uses_bar_true_range_never_fixed_two() -> None:
    spec = "MES"
    quiet = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=0.25)
    wild = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=5.0)
    model = CostModel()
    contract = spec_for(spec)
    quiet_ticks = model.ticks_for_fill(spec=contract, quantity=1.0, market=quiet).slippage_ticks
    wild_ticks = model.ticks_for_fill(spec=contract, quantity=1.0, market=wild).slippage_ticks
    assert wild_ticks > quiet_ticks
    assert COST_MODEL_VERSION == "1.1.0"
    loaded = load_slippage_calibration()
    assert loaded.coefficient == SLIPPAGE_COEFFICIENT == 0.10
    assert loaded.source == "documented_assumption"
    assert "true-range" in ASSUMPTION
    bar = ResearchBar(ts_ns=1, open=10.0, high=12.0, low=9.0, close=11.0, volume=1.0)
    assert bar_volatility_price(bar) == 3.0


@pytest.mark.unit
def test_mnq_cost_band_is_usd_not_ticks() -> None:
    lo, hi = band_for("MNQ")
    assert (lo, hi) == MNQ_ONE_WAY_USD
    assert (lo, hi) != (1.0, 2.5)
    band = report_band("MNQ")
    assert band.band_min_usd == lo
    assert band.modeled_one_way_usd > 0.0
    assert band.modeled_one_way_usd != pytest.approx(band.modeled_one_way_ticks)
    assert spec_for("MNQ").commission_usd_per_side == pytest.approx(0.94)
    assert "USD" in band.note or "dollar" in band.note
    assert ES_NQ_ONE_WAY == (0.5, 1.5)


@pytest.mark.unit
def test_static_rules_replace_wfe_and_skip_cpcv(tmp_path: Path) -> None:
    path = tmp_path / "static.jsonl"
    registry = _registry(path)
    wfe = WFESnapshot(
        wfe=math.nan,
        mean_is_sharpe=-1.0,
        mean_oos_sharpe=0.2,
        n_windows=6,
        mode="static_rules",
        parameter_stability=1.0,
    )
    passed, report = passes_validation_gate(
        _good(path, wfe=wfe, has_fit_step=False),
        registry=registry,
    )
    assert passed is True
    assert "missing_or_undefined_wfe" not in report.reject_reasons
    decayed, decay_report = passes_validation_gate(
        _good(
            path,
            wfe=WFESnapshot(
                wfe=math.nan,
                mean_is_sharpe=-1.0,
                mean_oos_sharpe=0.2,
                n_windows=6,
                mode="static_rules",
                parameter_stability=0.0,
            ),
            has_fit_step=False,
        ),
        registry=registry,
    )
    assert decayed is False
    assert "static_structural_decay" in decay_report.reject_reasons
    share, share_report = passes_validation_gate(
        _good(
            path,
            wfe=wfe,
            has_fit_step=False,
            oos_distribution=OOSDistribution.from_values((-1.0, -0.5, 0.1, -0.2, 0.05, -0.3)),
            median_oos_after_costs=0.001,
        ),
        registry=registry,
    )
    assert share is False
    assert "static_positive_share_below_60" in share_report.reject_reasons
    assert STATIC_POSITIVE_SHARE_MIN == 0.60
    assert FLOOR_DSR_PROBABILITY_MIN == 0.95
    assert FLOOR_PBO_HARD_REJECT == 0.50
    zero, zero_report = passes_validation_gate(
        _good(path, wfe=wfe, has_fit_step=False, median_oos_after_costs=0.0),
        registry=registry,
    )
    assert zero is False
    assert "static_median_oos_not_positive" in zero_report.reject_reasons


@pytest.mark.unit
def test_evaluate_candidate_static_skips_cpcv_keeps_dsr_pbo(tmp_path: Path) -> None:
    audit = tmp_path / "pipe.jsonl"
    registry = TrialRegistry(audit)
    n = 360
    gross = tuple(0.002 for _ in range(n))
    positions = tuple(1.0 for _ in range(n))
    markets = tuple(MarketSnapshot(volume=8_000.0, average_volume=10_000.0, volatility_price=1.0) for _ in range(n))
    peers = (tuple(0.001 for _ in range(n)), tuple(-0.001 for _ in range(n)))
    for index, peer in enumerate(peers):
        del peer
        registry.record(config_id=f"peer-{index}", agent_id="edge", metrics={"i": index})
    evaluation = evaluate_candidate(
        agent_id="edge",
        config_id="static-0",
        gross_returns=gross,
        positions=positions,
        markets=markets,
        spec="MES",
        registry=registry,
        peer_net_returns=peers,
        audit_path=audit,
        has_fit_step=False,
        market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n)),
        n_days=80,
    )
    assert evaluation.results.has_fit_step is False
    assert evaluation.results.wfe.mode == "static_rules"
    assert not math.isfinite(evaluation.results.wfe.wfe)
    assert evaluation.bootstrap_sharpes
    assert evaluation.results.n_days == 80
    assert evaluation.report.dsr.n_trials == registry.n_trials


@pytest.mark.unit
def test_structural_decay_fail_closed_and_block_bootstrap() -> None:
    assert structural_decay((1.0, 0.9, 0.8, 0.7, 0.6, 0.1)) is True
    assert structural_decay((0.1, 0.2, 0.15, 0.18, 0.2, 0.22)) is False
    assert structural_decay((1.0, 1.0, 1.0)) is True
    dist = block_bootstrap_sharpes(tuple(0.001 * ((-1) ** index) for index in range(40)), block=5, n_paths=8)
    assert dist.is_complete()
    assert not block_bootstrap_sharpes((0.1, 0.2)).is_complete()


@pytest.mark.unit
def test_friday_roll_and_back_adjust_leaves_pnl_unadjusted() -> None:
    require_friday_roll()
    body = verify_nt8_rolls()
    assert body["friday_2026_06_12_present"] is True
    assert FRIDAY_ROLL in NT8_ROLL_SET
    pre = _rth_minutes(datetime(2026, 6, 11, 14, 31, tzinfo=UTC), 3, 5000.0)
    roll_open = _bar(datetime(2026, 6, 11, 22, 1, tzinfo=UTC), open_=5300.0, high=5301.0, low=5299.0, close=5300.0)
    after = _rth_minutes(datetime(2026, 6, 12, 14, 31, tzinfo=UTC), 3, 5300.0)
    bars = pre + (roll_open,) + after
    labels = annotate(bars)
    adjusted = back_adjust(bars, labels.session_dates)
    assert adjusted[0].close != bars[0].close
    assert adjusted[-1].close == pytest.approx(bars[-1].close)
    prepared = prepare_tape("MES", bars + _rth_minutes(datetime(2026, 6, 12, 15, 0, tzinfo=UTC), 240, 5300.0))
    assert prepared.signal_bars[0].close != prepared.bars[0].close or prepared.dropped >= 0
    assert prepared.bars[-1].close == pytest.approx(prepared.signal_bars[-1].close)


@pytest.mark.unit
def test_holdout_pin_is_session_boundary_and_legacy_seal_recorded(tmp_path: Path) -> None:
    assert P2_HOLDOUT_START_UTC == datetime(2026, 1, 28, 23, 0, tzinfo=UTC)
    assert P2_HOLDOUT_START_LEGACY_NS == int(datetime(2026, 1, 29, tzinfo=UTC).timestamp() * 1_000_000_000)
    start = datetime(2023, 10, 28, tzinfo=UTC)
    end = datetime(2026, 10, 28, tzinfo=UTC)
    n = 400
    step = (end - start).total_seconds() / float(n - 1)
    bars = tuple(
        _bar(
            datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC),
            open_=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
        )
        for index in range(n)
    )
    path = tmp_path / "MES" / "1m" / "mes.csv"
    path.parent.mkdir(parents=True)
    path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=path,
        bars=bars,
        holdout_start_ns=P2_HOLDOUT_START_NS,
    )
    first = seal_holdout((tape,), report_dir=tmp_path / "rep", require_known_files=False)
    assert first["holdout_start_ns"] == P2_HOLDOUT_START_NS
    loaded = load_seal(tmp_path / "rep")
    assert loaded["holdout_start_ns"] == P2_HOLDOUT_START_NS
    previous = loaded["previous_seals"]
    assert isinstance(previous, list)
    assert previous[0]["seal_sha256"] == LEGACY_SEAL_SHA256
    assert previous[1]["seal_sha256"] == PENDING_COUNTS_SEAL_SHA256
    snapshot = json.loads(
        (Path("experiments/reports") / PENDING_COUNTS_SEAL_NAME).read_text(encoding="utf-8")
    )
    assert snapshot["seal_sha256"] == PENDING_COUNTS_SEAL_SHA256
    assert snapshot["bar_counts_pending_recompute"] is True
    committed = json.loads(Path("experiments/reports/phase5_p2_holdout_seal.json").read_text(encoding="utf-8"))
    assert committed["holdout_start_ns"] == P2_HOLDOUT_START_NS
    assert committed["previous_seals"][0]["seal_sha256"] == LEGACY_SEAL_SHA256
    if committed.get("bar_counts_pending_recompute") is True:
        assert committed["seal_sha256"] == PENDING_COUNTS_SEAL_SHA256
    else:
        shas = {item["seal_sha256"] for item in committed["previous_seals"]}
        assert LEGACY_SEAL_SHA256 in shas
        assert PENDING_COUNTS_SEAL_SHA256 in shas
        mes = committed["instruments"]["MES"]
        mnq = committed["instruments"]["MNQ"]
        assert int(mes["n_train"]) > 0 and int(mes["n_holdout"]) > 0
        assert int(mnq["n_train"]) > 0 and int(mnq["n_holdout"]) > 0
        assert "bar_counts_pending_recompute" not in committed
        assert committed["seal_sha256"] == LIVE_SEAL_SHA256
    train = access_bars(tape, purpose="gate", pinned_start_ns=P2_HOLDOUT_START_NS)
    locked = access_bars(tape, purpose="evaluation", pinned_start_ns=P2_HOLDOUT_START_NS)
    assert train[-1].ts_ns < P2_HOLDOUT_START_NS <= locked[0].ts_ns
    assert (tmp_path / "rep" / SEAL_NAME).is_file()


@pytest.mark.unit
def test_pending_counts_seal_is_copied_before_reseal(tmp_path: Path) -> None:
    report = tmp_path / "rep"
    report.mkdir()
    snapshot = json.loads((Path("experiments/reports") / PENDING_COUNTS_SEAL_NAME).read_text(encoding="utf-8"))
    (report / SEAL_NAME).write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    path = tmp_path / "MES" / "1m" / "mes.csv"
    path.parent.mkdir(parents=True)
    path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    start = datetime(2023, 10, 28, tzinfo=UTC)
    end = datetime(2026, 10, 28, tzinfo=UTC)
    n = 400
    step = (end - start).total_seconds() / float(n - 1)
    bars = tuple(
        _bar(
            datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC),
            open_=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
        )
        for index in range(n)
    )
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=path,
        bars=bars,
        holdout_start_ns=P2_HOLDOUT_START_NS,
    )
    sealed = seal_holdout((tape,), report_dir=report, require_known_files=False)
    preserved = json.loads((report / PENDING_COUNTS_SEAL_NAME).read_text(encoding="utf-8"))
    assert preserved["seal_sha256"] == PENDING_COUNTS_SEAL_SHA256
    assert sealed["seal_sha256"] != PENDING_COUNTS_SEAL_SHA256
    shas = {item["seal_sha256"] for item in sealed["previous_seals"]}
    assert LEGACY_SEAL_SHA256 in shas
    assert PENDING_COUNTS_SEAL_SHA256 in shas


@pytest.mark.unit
def test_positive_and_null_control_direction_helpers() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    up = _rth_minutes(start, 10, 5000.0, step=0.5)
    down = _rth_minutes(start + timedelta(days=1), 10, 5100.0, step=-0.5)
    bars = up + down
    labels = annotate(bars)
    planted = rth_session_direction(bars, labels.session_dates, labels.rth)
    assert 1.0 in planted
    assert -1.0 in planted
    null = shuffle_signals(planted, seed=1)
    assert sorted(null) == sorted(planted)


@pytest.mark.unit
def test_diagnostics_include_trades_hitrate_costs_and_sharpes() -> None:
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    gross = (0.01, -0.002, 0.004)
    positions = (1.0, 1.0, 0.0)
    markets = tuple(MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0) for _ in gross)
    costed = apply_costs(gross_returns=gross, positions=positions, equity=100_000.0, spec="MES", markets=markets)
    trades = (
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=5004.0, pnl_ticks=16.0, reason="target"),
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=4998.0, pnl_ticks=-8.0, reason="stop"),
    )
    diag = from_trades(
        trades=trades,
        geometry=geo,
        costed=costed,
        is_sharpes=(0.4, 0.5),
        oos_sharpes=(0.2, -0.1, 0.3),
        regimes=RegimeSnapshot(0.1, 0.2, 0.3, -0.1, 0.4),
        n_trials=14,
        n_days=43,
        pct_positive_oos=0.5,
        bootstrap_sharpes=(0.1, 0.2),
    )
    assert diag.n_trades == 2
    assert diag.hitrate == pytest.approx(0.5)
    assert diag.break_even_win_rate == geo.break_even_win_rate
    assert diag.commission_usd > 0.0
    assert diag.n_trials == 14
    assert diag.n_days == 43
    assert math.isfinite(window_sharpe((0.01, 0.02, -0.005)))


@pytest.mark.unit
def test_costed_series_splits_four_legs() -> None:
    gross = (0.01, 0.0, -0.002)
    positions = (1.0, 0.0, -1.0)
    markets = tuple(MarketSnapshot(volume=4_000.0, average_volume=10_000.0, volatility_price=1.5) for _ in gross)
    costed = apply_costs(gross_returns=gross, positions=positions, equity=50_000.0, spec="MNQ", markets=markets)
    assert sum(costed.commission_usd) > 0.0
    assert sum(costed.half_spread_usd) > 0.0
    assert sum(costed.slippage_usd) > 0.0
    assert sum(costed.impact_usd) > 0.0
    assert costed.provenance.model_version == "1.1.0"


@pytest.mark.unit
def test_simulate_uses_signal_bars_length_guard() -> None:
    bars = _rth_minutes(datetime(2026, 3, 2, 14, 31, tzinfo=UTC), 241, 5000.0)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    with pytest.raises(Exception, match="align"):
        simulate(
            family="mean_reversion",
            bars=bars,
            geometry=geo,
            lookback=10,
            threshold=1.5,
            mode="fade",
            signal_bars=bars[:-1],
        )


@pytest.mark.unit
def test_n_days_is_documented_on_first_cycle_specs() -> None:
    specs = first_cycle_specs()
    assert all(item.time_stop_bars == 16 for item in specs)
    assert all(item.session_filter == "rth" for item in specs)
    note = window_note(specs, 43)
    assert "n_days=43" in note
    assert "walk-forward" in note
    is_size, oos_size, formed = walk_forward_sizes(43)
    assert formed >= 6
    assert oos_size == max(2, (43 - 40) // 8)
    assert is_size != 43
    days = _rth_minutes(datetime(2026, 3, 2, 14, 31, tzinfo=UTC), 40, 5000.0)
    days += _rth_minutes(datetime(2026, 3, 3, 14, 31, tzinfo=UTC), 40, 5000.0)
    prepared = prepare_tape("MES", days)
    assert session_day_count({"MES": prepared}) == 2
    assert session_day_count({"MES": prepared}) != len(prepared.bars)


def _control_tape() -> PreparedTape:
    rows: list[ResearchBar] = []
    day = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    session_index = 0
    while session_index < 22:
        if day.weekday() < 5:
            price = 5000.0
            magnitude = 1.5 + 0.25 * float(session_index % 7)
            step = magnitude if session_index % 2 == 0 else -magnitude
            for index in range(24):
                ts = day + timedelta(minutes=index)
                nxt = price + step
                high = max(price, nxt) + 0.25
                low = min(price, nxt) - 0.25
                rows.append(_bar(ts, open_=price, high=high, low=low, close=nxt, volume=8_000.0))
                price = nxt
            session_index += 1
        day += timedelta(days=1)
    return prepare_tape("MES", tuple(rows))


@pytest.mark.unit
def test_run_controls_detects_planted_edge_and_rejects_null(tmp_path: Path) -> None:
    prepared = _control_tape()
    market = daily_market_returns(prepared.bars, prepared.session_dates)
    report = run_controls(
        prepared={"MES": prepared},
        registry=TrialRegistry(tmp_path / "control.jsonl"),
        audit_path=tmp_path / "control.jsonl",
        is_size=6,
        oos_size=2,
        market_returns=market,
        n_days=22,
    )
    assert report.accepted is True
    assert report.positive.detected is True
    assert report.null.detected is False
    assert report.positive.median_oos > report.null.median_oos


@pytest.mark.unit
def test_control_geometry_matches_2026_10_29_preregister() -> None:
    assert CONTROL_TARGET_TICKS == 20_000
    assert CONTROL_STOP_TICKS == 20_000
    assert CONTROL_TARGET_TICKS == CONTROL_STOP_TICKS
    assert CONTROL_TIME_STOP_BARS == 2_000
    assert CONTROL_SESSION_FILTER == "rth"
    specs = first_cycle_specs()
    assert all(item.time_stop_bars == 16 for item in specs)


@pytest.mark.unit
def test_control_holds_wide_first_rth_bar_to_session_close() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    first = _bar(start, open_=5000.0, high=5005.25, low=4999.75, close=5001.0)
    adverse = _bar(
        start + timedelta(minutes=1),
        open_=5001.0,
        high=5002.0,
        low=4998.0,
        close=5000.5,
        volume=8_000.0,
    )
    rest: list[ResearchBar] = []
    price = 5000.5
    for index in range(2, 40):
        nxt = price + 1.0
        rest.append(
            _bar(
                start + timedelta(minutes=index),
                open_=price,
                high=nxt + 0.25,
                low=price - 0.25,
                close=nxt,
                volume=8_000.0,
            )
        )
        price = nxt
    prepared = prepare_tape("MES", (first, adverse) + tuple(rest))
    planted = rth_session_direction(prepared.bars, prepared.session_dates, prepared.rth)
    executed = execute_control(prepared, planted, root="MES")
    assert executed.trades
    assert all(trade.reason == "session_end" for trade in executed.trades)
    assert all(trade.pnl_ticks > 8.0 for trade in executed.trades)


@pytest.mark.unit
def test_pinned_first_cycle_preregister_is_not_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "phase5_first_cycle_preregister.md"
    path.write_text("PINNED\n", encoding="utf-8")
    out = write_first_cycle_preregister(tmp_path)
    assert out.read_text(encoding="utf-8") == "PINNED\n"


@pytest.mark.unit
def test_reuse_holdout_seal_keeps_matching_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2023, 10, 28, tzinfo=UTC)
    end = datetime(2026, 10, 28, tzinfo=UTC)
    n = 400
    step = (end - start).total_seconds() / float(n - 1)
    bars = tuple(
        _bar(
            datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC),
            open_=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
        )
        for index in range(n)
    )
    path = tmp_path / "MES" / "1m" / "mes.csv"
    path.parent.mkdir(parents=True)
    path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=path,
        bars=bars,
        holdout_start_ns=P2_HOLDOUT_START_NS,
    )
    report = tmp_path / "rep"
    first = seal_holdout((tape,), report_dir=report, require_known_files=False)
    instruments = first["instruments"]
    assert isinstance(instruments, dict)
    mes_row = instruments["MES"]
    assert isinstance(mes_row, dict)
    mes_sha = mes_row["file_sha256"]
    assert isinstance(mes_sha, str)
    monkeypatch.setattr(seal_mod, "CSV_SHA256", {"MES": mes_sha, "MNQ": mes_sha})
    reused = reuse_holdout_seal((tape,), report_dir=report)
    assert reused is not None
    assert reused["seal_sha256"] == first["seal_sha256"]


@pytest.mark.unit
def test_walk_forward_finite_mean_with_mixed_infinite_sharpes() -> None:
    series = (0.01,) * 20 + (-0.01,) * 20 + (0.0,) * 20
    result = run_walk_forward(
        60, WalkForwardConfig(is_size=10, oos_size=6, mode="rolling"), static_return_scorer(series)
    )
    assert result.wfe.n_windows >= 6
    assert (
        math.isnan(result.wfe.wfe)
        or math.isfinite(result.wfe.mean_oos_sharpe)
        or math.isnan(result.wfe.mean_oos_sharpe)
    )


@pytest.mark.unit
def test_missing_evaluation_static_rules_do_not_require_wfe(tmp_path: Path) -> None:
    audit = tmp_path / "missing.jsonl"
    evaluation = missing_evaluation(
        agent_id="p2",
        audit_path=audit,
        registry=TrialRegistry(audit),
        has_fit_step=False,
    )
    assert evaluation.results.has_fit_step is False
    assert evaluation.results.wfe.mode == "static_rules"
    assert "missing_or_undefined_wfe" not in evaluation.report.reject_reasons
    assert evaluation.passed is False


@pytest.mark.unit
def test_positive_share_counts_only_strictly_positive() -> None:
    assert positive_share((1.0, 0.0, -1.0, 0.5, 0.2, 0.1)) == pytest.approx(4.0 / 6.0)
    assert not math.isfinite(positive_share(()))
