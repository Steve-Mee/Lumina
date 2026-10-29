"""Fail-closed kill battery for P2 artefact-fix modules."""

from __future__ import annotations

import hashlib
import inspect
import math
import random
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from lumina_research.cycles.adjust import back_adjust
from lumina_research.cycles.catalog import catalog
from lumina_research.cycles.cost_bands import (
    ES_NQ_ONE_WAY,
    ES_ONE_WAY_USD,
    MES_MNQ_ONE_WAY,
    MES_ONE_WAY_USD,
    MNQ_ONE_WAY_USD,
    NQ_ONE_WAY_USD,
    REFERENCE_NOTIONAL_USD,
    band_for,
    report_band,
)
from lumina_research.cycles.data import LoadedTape, ResearchBar
from lumina_research.cycles.atr import ATR_N_SESSIONS, causal_session_atr, points_to_ticks
from lumina_research.cycles.atr_cycle import ATR_SEAL_NAME, atr_es_specs
from lumina_research.cycles.diagnostics import from_trades
from lumina_research.cycles.execution import (
    ClosedTrade,
    ExecutionRefused,
    _Book,
    _session_end_flags,
    bar_volatility_price,
    causal_session_adv,
    run_execution,
)
from lumina_research.cycles.fills import (
    FILL_POLICY,
    FillRefused,
    fill_probability,
    touch_fill,
    trade_through_fill,
    traded_through,
)
from lumina_research.cycles.gaps import in_known_gap
from lumina_research.cycles.geometry import GeometryRefused, floors_for, require_geometry
from lumina_research.cycles.holdout import (
    DAYS_PER_MONTH,
    HOLDOUT_MONTHS,
    HOLDOUT_MONTHS_MAX,
    HOLDOUT_MONTHS_MIN,
    NS_PER_DAY,
    P2_HOLDOUT_START_LEGACY_NS,
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    HoldoutLocked,
    access_bars,
    assert_not_holdout,
    holdout_ns,
    split_holdout,
)
from lumina_research.cycles.null_model import (
    NULL_A2_MAX_SHARE,
    NULL_N_SEEDS,
    default_null_seeds,
    majority_a2_cap,
    max_a2_hits,
)
from lumina_research.cycles.positive_control import (
    CONTROL_ATR_MULTIPLE,
    CONTROL_STOP_TICKS,
    CONTROL_TARGET_TICKS,
    CONTROL_TIME_STOP_BARS,
    _detected,
    execute_control,
    rth_session_direction,
    shuffle_signals,
)
from lumina_research.cycles.prepare import _high_vol_sessions, _quiet_mask, prepare_tape
from lumina_research.cycles.roll_verify import FRIDAY_ROLL, require_friday_roll, verify_nt8_rolls
from lumina_research.cycles.rolls import NT8_ROLL_DATES, NT8_ROLL_SET, is_roll_session
from lumina_research.monitoring.acceptance import (
    HIGH_VOL_REALIZED_WINDOW,
    HIGH_VOL_TRAILING_PCT,
    HIGH_VOL_TRAILING_WINDOW,
)
from lumina_research.cycles.seal import (
    LEGACY_SEAL_SHA256,
    LIVE_SEAL_SHA256,
    PENDING_COUNTS_SEAL_SHA256,
    file_sha256,
    load_seal,
    seal_holdout,
)
from lumina_research.cycles.sessions import (
    INTRASESSION_HOLE_NS,
    RTH_LAST_CLOSE_MIN,
    RTH_OPEN_CLOSE_MIN,
    annotate,
    is_rth_close,
)
from lumina_research.cycles.slippage_calibration import (
    ETH_SLIPPAGE_COEFFICIENT,
    SLIPPAGE_COEFFICIENT,
    load_slippage_calibration,
    reference_market,
)
from lumina_research.validation.block_bootstrap import DEFAULT_BLOCK, DEFAULT_PATHS, block_bootstrap_sharpes
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import (
    COST_COMPONENTS,
    COST_MODEL_ID,
    COST_MODEL_VERSION,
    MAX_VOLUME_SLIP_SCALE,
    CostModel,
    CostModelError,
    MarketSnapshot,
    apply_costs,
)
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.pipeline import _median, _turnover, evaluate_candidate
from lumina_research.validation.regimes import _finite_regime_sharpe, _rolling_vol, regime_robustness
from lumina_research.validation.static_rules import (
    STATIC_DECAY_SPEARMAN,
    STATIC_POSITIVE_SHARE_MIN,
    positive_share,
    spearman_rho,
    structural_decay,
)
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN, FLOOR_PBO_HARD_REJECT
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import (
    CostProvenance,
    DSRSnapshot,
    OOSDistribution,
    PBOSnapshot,
    RegimeSnapshot,
    ValidationResults,
    WFESnapshot,
)

UTC = timezone.utc


def _fail(message: str) -> None:
    raise AssertionError(message)


def _must_raise(exc: type[BaseException], fn: object, *args: object, **kwargs: object) -> None:
    try:
        fn(*args, **kwargs)  # type: ignore[operator]
    except exc:
        return
    _fail(f"{getattr(fn, '__name__', fn)} must raise {exc.__name__}")


def _bar(ts_ns: int, close: float, *, high: float | None = None, low: float | None = None) -> ResearchBar:
    hi = close + 0.5 if high is None else high
    lo = close - 0.5 if low is None else low
    return ResearchBar(ts_ns=ts_ns, open=close, high=hi, low=lo, close=close, volume=1_000.0)


def _provenance() -> CostProvenance:
    return CostProvenance(
        model_id=COST_MODEL_ID,
        model_version=COST_MODEL_VERSION,
        components=COST_COMPONENTS,
        applied=True,
        contract_root="MES",
        tick_size=0.25,
        tick_value_usd=1.25,
        commission_ticks=0.75,
    )


def _static_bundle(path: Path, **overrides: object) -> ValidationResults:
    payload: dict[str, object] = {
        "agent_id": "p2-mut",
        "audit_path": path,
        "oos_distribution": OOSDistribution.from_values((1.2, 0.9, 1.1, 0.8, 1.0, 0.95)),
        "dsr": DSRSnapshot(
            probability=0.97,
            observed_sr=0.2,
            expected_max_sr=0.05,
            sr_standard_error=0.04,
            n_trials=5,
            n_observations=300,
            skew=0.0,
            kurtosis=3.0,
            formulation="bailey_lopez_de_prado_2014",
        ),
        "pbo": PBOSnapshot(
            pbo=0.10,
            n_slices=8,
            n_combinations=70,
            n_configs=5,
            n_below_median=7,
            formulation="cscv_logit_bailey_2014",
            logit_mean=0.4,
        ),
        "wfe": WFESnapshot(
            wfe=math.nan,
            mean_is_sharpe=-1.2,
            mean_oos_sharpe=0.4,
            n_windows=6,
            mode="static_rules",
            parameter_stability=1.0,
        ),
        "cost_provenance": _provenance(),
        "median_oos_after_costs": 0.002,
        "n_oos_windows": 6,
        "regimes": RegimeSnapshot(0.8, 0.7, 0.9, 0.4, 0.7),
        "n_trials_registry": 5,
        "has_fit_step": False,
    }
    payload.update(overrides)
    return ValidationResults(**payload)  # type: ignore[arg-type]


def _ref_high_vol_sessions(closes: dict[date, float]) -> dict[date, bool]:
    """Unmutated copy of the 20d/75th causal high-vol label. Lives in the kill battery."""
    dates = tuple(sorted(closes))
    rets: list[float] = []
    for index, day in enumerate(dates):
        if index == 0:
            rets.append(0.0)
            continue
        prev = closes[dates[index - 1]]
        rets.append(0.0 if prev == 0.0 else (closes[day] - prev) / prev)
    window = HIGH_VOL_REALIZED_WINDOW
    trail = HIGH_VOL_TRAILING_WINDOW
    labels: dict[date, bool] = {}
    realized: list[float] = []
    for index, day in enumerate(dates):
        if index < window:
            labels[day] = False
            continue
        chunk = rets[index - window : index]
        current = float(statistics.pstdev(chunk)) if len(chunk) >= 2 else 0.0
        realized.append(current)
        history = realized[max(0, len(realized) - trail) : -1]
        if len(history) < 8:
            labels[day] = False
            continue
        ordered = sorted(history)
        cap_index = min(len(ordered) - 1, max(0, int(HIGH_VOL_TRAILING_PCT * (len(ordered) - 1))))
        labels[day] = current > ordered[cap_index]
    return labels


def _ref_block_sharpes(series: tuple[float, ...], *, block: int, n_paths: int, seed: int) -> tuple[float, ...]:
    n = len(series)
    rng = random.Random(seed)
    n_blocks = math.ceil(n / block)
    max_start = n - block
    sharpes: list[float] = []
    for _ in range(n_paths):
        stitched: list[float] = []
        for _step in range(n_blocks):
            start = rng.randint(0, max_start)
            stitched.extend(series[start : start + block])
        path = tuple(stitched[:n])
        sharpes.append(annualized_sharpe(path, periods_per_year=252.0))
    return tuple(sharpes)


def _kill_remaining_survivors() -> None:
    """Assertions that fail on the remaining non-equivalent AST mutants."""
    bar = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    if touch_fill(side=1.0, limit=9.6, bar=bar) is not True:
        _fail("buy touch must fill when low is strictly below the limit")
    if touch_fill(side=-1.0, limit=10.4, bar=bar) is not True:
        _fail("sell touch must fill when high is strictly above the limit")
    if trade_through_fill(side=0.0, limit=9.6, bar=bar, average_volume=50.0) is not False:
        _fail("flat trade_through_fill must return False")
    spec = spec_for("MES")
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    net_target = float(geo.target_ticks) - geo.roundtrip_cost_ticks
    net_stop = float(geo.stop_ticks) + geo.roundtrip_cost_ticks
    denom = net_target + net_stop
    expected_be = net_stop / denom
    if abs(geo.break_even_win_rate - expected_be) > 1e-12:
        _fail("break-even must be net_stop / (net_target + net_stop)")
    if not 0.0 < geo.break_even_win_rate < 1.0:
        _fail("normal geometry break-even must sit in (0, 1)")
    if abs(geo.net_target_usd - net_target * spec.tick_value_usd) > 1e-12:
        _fail("net_target_usd must be net ticks * tick_value")
    if abs(geo.net_stop_usd - net_stop * spec.tick_value_usd) > 1e-12:
        _fail("net_stop_usd must be net ticks * tick_value")
    mes_band = report_band("MES")
    if abs(mes_band.modeled_one_way_usd - mes_band.modeled_one_way_ticks * spec.tick_value_usd) > 1e-9:
        _fail("modeled USD must be ticks * tick_value")
    if abs(mes_band.commission_usd_per_contract_per_side - 0.94) > 1e-9:
        _fail("MES commission must be ADR-0055 $0.94/side")
    if abs(report_band("ES").commission_usd_per_contract_per_side - 2.87) > 1e-9:
        _fail("ES commission must be ADR-0055 $2.87/side")
    if abs(report_band("MNQ").commission_usd_round_trip - 1.88) > 1e-9:
        _fail("MNQ round-trip commission must be $1.88")
    expected_bp = 10_000.0 * mes_band.modeled_one_way_usd / REFERENCE_NOTIONAL_USD["MES"]
    if abs(mes_band.modeled_one_way_bp - expected_bp) > 1e-9:
        _fail("modeled bp must be 10000 * usd / notional")
    if mes_band.in_band is not True:
        _fail("modeled MES one-way USD must sit inside the dollar band")
    eight = tuple(0.001 * (1.0 if index % 2 == 0 else -0.4) for index in range(8))
    boot = block_bootstrap_sharpes(eight, block=5, n_paths=8, seed=20261029)
    expected_boot = _ref_block_sharpes(eight, block=5, n_paths=8, seed=20261029)
    if boot.values != expected_boot:
        _fail("block bootstrap must use ceil(n / block) blocks, not n * block")
    if _turnover((1.0,)) != 0.0:
        _fail("single-bar turnover must be 0")
    if abs(_turnover((0.0, 1.0, 0.0)) - 1.0) > 1e-12:
        _fail("turnover must be mean absolute position change")
    if abs(_median((1.0, 3.0)) - 2.0) > 1e-12:
        _fail("even-length median must average the two central values")
    if abs(_median((1.0, 2.0, 3.0)) - 2.0) > 1e-12:
        _fail("odd-length median must return the central value")
    rho_tied = spearman_rho((3.0, 1.0, 1.0, 1.0, 2.0, 2.0))
    expected_rho = statistics.correlation((1.0, 2.0, 3.0, 4.0, 5.0, 6.0), (6.0, 2.0, 2.0, 2.0, 4.5, 4.5))
    if abs(rho_tied - expected_rho) > 1e-12:
        _fail("tied Spearman ranks must use average ranks")
    fake_nan = SimpleNamespace(
        report=SimpleNamespace(
            median_oos_after_costs=math.nan,
            oos_distribution=SimpleNamespace(pct_positive=0.9, values=(0.2, 0.1, 0.3, 0.05, 0.15, 0.12)),
        )
    )
    if _detected(fake_nan, null_median=None) is not False:  # type: ignore[arg-type]
        _fail("non-finite planted median must not count as detected")
    fake_pct = SimpleNamespace(
        report=SimpleNamespace(
            median_oos_after_costs=0.2,
            oos_distribution=SimpleNamespace(pct_positive=math.nan, values=(0.2, 0.1, 0.3, 0.05, 0.15, 0.12)),
        )
    )
    if _detected(fake_pct, null_median=None) is not False:  # type: ignore[arg-type]
        _fail("non-finite planted share must not count as detected")
    market_up = tuple(0.01 for _ in range(40))
    net_up = tuple(0.001 for _ in range(40))
    empty_down = regime_robustness(net_up, market_returns=market_up)
    if math.isfinite(empty_down.robustness):
        _fail("empty trend-down bucket must leave robustness undefined")
    market_split = tuple(-0.03 if index < 20 else 0.03 for index in range(40))
    net_split = tuple(0.04 if index < 20 else -0.02 for index in range(40))
    trend_snap = regime_robustness(net_split, market_returns=market_split)
    if trend_snap.trend_down_sharpe <= trend_snap.trend_up_sharpe:
        _fail("profits in the down-market half must show trend_down > trend_up")
    market_vol = tuple(0.001 if index < 20 else (0.06 if index % 2 == 0 else -0.06) for index in range(40))
    net_vol = tuple(-0.02 if index < 20 else 0.03 for index in range(40))
    vol_snap = regime_robustness(net_vol, market_returns=market_vol)
    if vol_snap.vol_high_sharpe <= vol_snap.vol_low_sharpe:
        _fail("profits in the high-vol half must show vol_high > vol_low")
    rolling = _rolling_vol(market_vol, 20)
    finite_vol = tuple(item for item in rolling if math.isfinite(item))
    median_vol = statistics.median(finite_vol)
    high_rets = tuple(
        net_vol[index]
        for index in range(len(net_vol))
        if rolling[index] >= median_vol and math.isfinite(rolling[index])
    )
    low_rets = tuple(
        net_vol[index] for index in range(len(net_vol)) if rolling[index] < median_vol and math.isfinite(rolling[index])
    )
    expected_high = _finite_regime_sharpe(annualized_sharpe(high_rets))
    expected_low = _finite_regime_sharpe(annualized_sharpe(low_rets))
    if abs(vol_snap.vol_high_sharpe - expected_high) > 1e-12:
        _fail("high-vol bucket must be vol >= median AND finite, not an OR")
    if abs(vol_snap.vol_low_sharpe - expected_low) > 1e-12:
        _fail("low-vol bucket must be vol < median AND finite, not an OR")
    mixed_market = tuple(0.02 if index % 3 == 0 else -0.01 for index in range(40))
    mixed_net = tuple(0.01 if index % 2 == 0 else -0.004 for index in range(40))
    formula_snap = regime_robustness(mixed_net, market_returns=mixed_market)
    parts = (
        formula_snap.vol_high_sharpe,
        formula_snap.vol_low_sharpe,
        formula_snap.trend_up_sharpe,
        formula_snap.trend_down_sharpe,
    )
    if all(math.isfinite(part) for part in parts):
        positive = sum(1.0 for part in parts if part > 0.0)
        worst = min(parts)
        expected_r = 0.5 * (positive / 4.0) + 0.5 * (1.0 / (1.0 + math.exp(-worst)))
        if abs(formula_snap.robustness - expected_r) > 1e-12:
            _fail("regime robustness formula drifted")
    pin_last = tuple(
        ResearchBar(ts_ns=index + 1, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0) for index in range(5)
    )
    _must_raise(HoldoutLocked, split_holdout, pin_last, pinned_start_ns=int(pin_last[-1].ts_ns))
    messy = (
        ResearchBar(ts_ns=10, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
        ResearchBar(ts_ns=30, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
        ResearchBar(ts_ns=20, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
        ResearchBar(ts_ns=40, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
    )
    _must_raise(HoldoutLocked, split_holdout, messy, pinned_start_ns=25)
    roll_start = datetime(2026, 6, 12, 14, 31, tzinfo=UTC)
    roll_bars = tuple(
        ResearchBar(
            ts_ns=int((roll_start.timestamp() + index * 60) * 1_000_000_000),
            open=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
            volume=5_000.0,
        )
        for index in range(4)
    )
    if not is_roll_session(annotate(roll_bars).session_dates[0]):
        _fail("2026-06-12 RTH bars must be the Friday roll session")
    rolled = prepare_tape("MES", roll_bars)
    if rolled.breaks[0] is not True:
        _fail("first bar of a roll session must break")
    if rolled.breaks[1] is not False:
        _fail("later bars of the same roll session must not be roll-breaks")
    globex_ts = datetime(2026, 3, 2, 13, 0, tzinfo=UTC)
    rth_ts = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    overnight = (
        ResearchBar(
            ts_ns=int(globex_ts.timestamp() * 1_000_000_000),
            open=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int(rth_ts.timestamp() * 1_000_000_000),
            open=5001.0,
            high=5001.5,
            low=5000.5,
            close=5001.0,
            volume=5_000.0,
        ),
    ) + tuple(
        ResearchBar(
            ts_ns=int((rth_ts.timestamp() + (index + 1) * 60) * 1_000_000_000),
            open=5001.0,
            high=5001.5,
            low=5000.5,
            close=5001.0,
            volume=5_000.0,
        )
        for index in range(3)
    )
    overnight_tape = prepare_tape("MES", overnight)
    if overnight_tape.breaks[1] is not False:
        _fail("Globex-to-RTH overnight gap must not count as an RTH intra-session hole")
    day = datetime(2025, 1, 6, 15, 0, tzinfo=UTC)
    daily: list[ResearchBar] = []
    made = 0
    while made < 40:
        if day.weekday() < 5:
            close = 5000.0 + float(made % 4) * 0.25 if made < 25 else 5000.0 + float(made - 24) * 80.0
            daily.append(
                ResearchBar(
                    ts_ns=int(day.timestamp() * 1_000_000_000),
                    open=close,
                    high=close + 0.5,
                    low=close - 0.5,
                    close=close,
                    volume=5_000.0,
                )
            )
            made += 1
        day += timedelta(days=1)
    daily_bars = tuple(daily)
    labels = annotate(daily_bars)
    closes = {session: bar.close for bar, session in zip(daily_bars, labels.session_dates, strict=True)}
    expected_high = _ref_high_vol_sessions(closes)
    got_high = _high_vol_sessions(closes)
    if got_high != expected_high:
        _fail("causal high-vol session labels drifted")
    quiet = _quiet_mask(daily_bars, labels.session_dates)
    for flag, session in zip(quiet, labels.session_dates, strict=True):
        if flag is expected_high.get(session, False):
            _fail("quiet mask must be the inverse of high-vol")
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    exec_bars = tuple(
        ResearchBar(
            ts_ns=int((start.timestamp() + index * 60) * 1_000_000_000),
            open=5000.0 + index * 0.05,
            high=5000.5 + index * 0.05,
            low=4999.5 + index * 0.05,
            close=5000.0 + index * 0.05,
            volume=5_000.0,
        )
        for index in range(8)
    )
    allow = annotate(exec_bars).rth
    if any(_session_end_flags(annotate(exec_bars).session_dates, allow, False)):
        _fail("session_end_flatten=False must not mark any session-end flags")
    held = run_execution(
        bars=exec_bars,
        signals=(1.0,) + (0.0,) * 7,
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=tuple(False for _ in exec_bars),
        rth=allow,
        session_dates=annotate(exec_bars).session_dates,
        time_stop_bars=100,
        session_end_flatten=False,
    )
    if any(item.reason == "session_end" for item in held.trades):
        _fail("flatten-off book must not close as session_end")
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        audit = path / "g.jsonl"
        registry = TrialRegistry(audit)
        for index in range(5):
            registry.record(config_id=f"cfg-{index}", agent_id="p2-mut", metrics={"i": index})
        thin_wfe, thin_report = passes_validation_gate(
            _static_bundle(
                audit,
                wfe=WFESnapshot(
                    wfe=math.nan,
                    mean_is_sharpe=-1.2,
                    mean_oos_sharpe=0.4,
                    n_windows=5,
                    mode="static_rules",
                    parameter_stability=1.0,
                ),
                n_oos_windows=6,
            ),
            registry=registry,
        )
        if thin_wfe or "walk_forward_windows_below_min" not in thin_report.reject_reasons:
            _fail("wfe.n_windows below the packaged floor must reject")
        missing, missing_report = passes_validation_gate(
            _static_bundle(audit, cost_provenance=None),
            registry=registry,
        )
        if missing or "missing_costs" not in missing_report.reject_reasons:
            _fail("None cost_provenance must reject as missing_costs")
        arr = path / "arr"
        arr.mkdir()
        (arr / "phase5_p2_holdout_seal.json").write_text("[]", encoding="utf-8")
        _must_raise(HoldoutLocked, load_seal, arr)


def _kill_deeper() -> None:
    """Behavioral assertions aimed at the remaining mutation sites."""
    if ES_NQ_ONE_WAY != (0.5, 1.5) or MES_MNQ_ONE_WAY != (1.0, 2.5):
        _fail("informational tick conversions drifted")
    if band_for("MNQ") == MES_MNQ_ONE_WAY:
        _fail("MNQ USD band must not be the legacy tick interval")
    if band_for("ES") != ES_ONE_WAY_USD or band_for("NQ") != NQ_ONE_WAY_USD:
        _fail("ES/NQ USD bands drifted")
    if band_for("MES") != MES_ONE_WAY_USD:
        _fail("MES USD band drifted")
    mes_band = report_band("MES")
    if mes_band.modeled_one_way_usd <= 0.0 or mes_band.modeled_one_way_bp <= 0.0:
        _fail("modeled MES costs must be positive USD and bp")
    if mes_band.band_min_usd != MES_ONE_WAY_USD[0] or mes_band.band_max_usd != MES_ONE_WAY_USD[1]:
        _fail("report_band USD bounds drifted")
    mnq_band = report_band("MNQ")
    if not (mnq_band.band_min_usd <= mnq_band.modeled_one_way_usd <= mnq_band.band_max_usd) and mnq_band.in_band:
        _fail("in_band flag must match the USD interval")
    if NS_PER_DAY != 24 * 3600 * 1_000_000_000:
        _fail("NS_PER_DAY drifted")
    if HOLDOUT_MONTHS != 9 or HOLDOUT_MONTHS_MIN != 6 or HOLDOUT_MONTHS_MAX != 12:
        _fail("holdout month bounds drifted")
    expected_ns = int(float(HOLDOUT_MONTHS) * DAYS_PER_MONTH * float(NS_PER_DAY))
    if holdout_ns(HOLDOUT_MONTHS) != expected_ns:
        _fail("holdout_ns(9) must use months * days * ns")
    if P2_HOLDOUT_START_NS != int(P2_HOLDOUT_START_UTC.timestamp() * 1_000_000_000):
        _fail("holdout ns is not the 23:00Z pin")
    if P2_HOLDOUT_START_LEGACY_NS != int(datetime(2026, 1, 29, tzinfo=UTC).timestamp() * 1_000_000_000):
        _fail("legacy holdout ns drifted")
    default_time_stop = inspect.signature(run_execution).parameters["time_stop_bars"].default
    if default_time_stop != 16:
        _fail("execution default time-stop must stay 16 bars")
    src = inspect.getsource(execute_control)
    if CONTROL_TARGET_TICKS != 20_000 or CONTROL_STOP_TICKS != 20_000:
        _fail("control geometry must stay pre-registered 1:1 20000")
    if CONTROL_TARGET_TICKS != CONTROL_STOP_TICKS:
        _fail("control target/stop must stay 1:1")
    if CONTROL_TIME_STOP_BARS != 2_000:
        _fail("control time-stop must not clip one RTH session")
    if "CONTROL_TARGET_TICKS" not in src or "CONTROL_STOP_TICKS" not in src:
        _fail("execute_control must use pre-registered control geometry")
    if "CONTROL_TIME_STOP_BARS" not in src:
        _fail("execute_control must use pre-registered control time-stop")
    if CONTROL_ATR_MULTIPLE != 1.5:
        _fail("ATR control multiple must stay 1.5")
    if "CONTROL_ATR_MULTIPLE" not in src:
        _fail("execute_control must keep the ATR geometry path")
    if ATR_N_SESSIONS != 14:
        _fail("causal ATR window must stay 14 sessions")
    if NULL_N_SEEDS != 32 or len(default_null_seeds()) != 32:
        _fail("null seed count must stay pre-registered 32")
    if default_null_seeds()[0] != 20261029 or default_null_seeds()[-1] != 20261060:
        _fail("null seed base drifted")
    if abs(NULL_A2_MAX_SHARE - 0.10) > 1e-12 or max_a2_hits(32) != 3:
        _fail("null 10% diagnostic cap must stay floor(0.10*32)=3")
    if majority_a2_cap(32) != 16:
        _fail("null fail-closed cap must stay majority-not-A2 (16 of 32)")
    if INTRASESSION_HOLE_NS != 90 * 1_000_000_000:
        _fail("90s hole threshold drifted")
    if DEFAULT_BLOCK != 5 or DEFAULT_PATHS != 48:
        _fail("bootstrap defaults drifted")
    eight = tuple(0.001 * (1.0 if index % 2 == 0 else -0.4) for index in range(8))
    if not block_bootstrap_sharpes(eight, block=5, n_paths=8).is_complete():
        _fail("length-8 bootstrap must form a distribution")
    if block_bootstrap_sharpes(eight, n_paths=1).is_complete():
        _fail("n_paths=1 bootstrap must be missing")
    if block_bootstrap_sharpes(eight, block=0).is_complete():
        _fail("block=0 bootstrap must be missing")
    share = positive_share((1.0, 0.0, -1.0, 0.5, 0.2, 0.1))
    if abs(share - 4.0 / 6.0) > 1e-12:
        _fail("positive_share must count only strictly positive windows")
    if math.isfinite(spearman_rho((1.0, 2.0))):
        _fail("spearman_rho needs at least 3 points")
    if not structural_decay((1.0, 0.8, 0.6, 0.4, 0.2, 0.0, -0.2)):
        _fail("long falling path must be decay")
    thin = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=10.0)
    fat = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    if trade_through_fill(side=1.0, limit=9.6, bar=thin, average_volume=100.0) is not False:
        _fail("volume 10 vs ADV 100 must miss the 0.35 volume multiple")
    if trade_through_fill(side=1.0, limit=9.6, bar=fat, average_volume=100.0) is not True:
        _fail("full-size volume must fill a trade-through")
    if fill_probability(side=1.0, limit=9.6, bar=thin, average_volume=100.0) != 0.1:
        _fail("fill probability is min(1, volume/ADV)")
    if touch_fill(side=1.0, limit=9.5, bar=fat) is not True or traded_through(side=1.0, limit=9.5, bar=fat):
        _fail("touch inclusive vs trade-through exclusive drifted")
    if touch_fill(side=-1.0, limit=10.5, bar=fat) is not True or traded_through(side=-1.0, limit=10.5, bar=fat):
        _fail("sell touch inclusive vs trade-through exclusive drifted")
    geo_small = require_geometry(root="MES", target_ticks=3, stop_ticks=2)
    if geo_small.target_ticks != 3 or geo_small.stop_ticks != 2:
        _fail("pre-registered 3/2 must be accepted")
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    if not math.isfinite(geo.break_even_win_rate) or geo.break_even_win_rate <= 0.0:
        _fail("16/8 geometry must have a finite positive break-even")
    one_way = (
        CostModel()
        .ticks_for_fill(spec=spec_for("MES"), quantity=1.0, market=reference_market(spec_for("MES")))
        .total_ticks
    )
    if abs(geo.roundtrip_cost_ticks - 2.0 * one_way) > 1e-9:
        _fail("round-trip cost must be 2 * one-way ticks")
    trades = (
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=5004.0, pnl_ticks=16.0, reason="target"),
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=4998.0, pnl_ticks=-8.0, reason="stop"),
    )
    dummy_costed = apply_costs(
        gross_returns=(0.01, -0.002),
        positions=(1.0, 0.0),
        equity=100_000.0,
        spec="MES",
        markets=(
            MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0),
            MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0),
        ),
    )
    diag = from_trades(
        trades=trades,
        geometry=geo,
        costed=dummy_costed,
        is_sharpes=(0.4,),
        oos_sharpes=(0.2,),
        regimes=RegimeSnapshot(0.1, 0.2, 0.3, -0.1, 0.4),
        n_trials=5,
        n_days=10,
        pct_positive_oos=0.5,
    )
    if diag.hitrate != 0.5:
        _fail("hitrate must count pnl_ticks > 0, not losses")
    if diag.n_trades != 2:
        _fail("n_trades drifted")
    if diag.exit_target != 1 or diag.exit_stop != 1:
        _fail("exit-reason counts must follow ClosedTrade.reason")
    if abs(diag.gross_ticks - 8.0) > 1e-12:
        _fail("gross_ticks must sum pnl_ticks")
    if abs(diag.gross_points - 8.0 * geo.tick_size) > 1e-12:
        _fail("gross_points must be gross_ticks * tick_size")
    three = (
        trades[0],
        trades[0],
        trades[1],
    )
    three_diag = from_trades(
        trades=three,
        geometry=geo,
        costed=dummy_costed,
        is_sharpes=(0.4,),
        oos_sharpes=(0.2,),
        regimes=RegimeSnapshot(0.1, 0.2, 0.3, -0.1, 0.4),
        n_trials=5,
        n_days=10,
        pct_positive_oos=0.5,
    )
    if abs(three_diag.hitrate - 2.0 / 3.0) > 1e-12:
        _fail("unbalanced hitrate must be wins/n_trades")
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    stop_entry = 5000.0
    stop_px = stop_entry - 8 * 0.25
    stop_bars = (
        ResearchBar(
            ts_ns=int(start.timestamp() * 1_000_000_000),
            open=stop_entry,
            high=stop_entry + 0.25,
            low=stop_entry - 0.25,
            close=stop_entry,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int((start.timestamp() + 60) * 1_000_000_000),
            open=stop_entry - 0.1,
            high=stop_entry,
            low=stop_entry - 0.1,
            close=stop_entry - 0.1,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int((start.timestamp() + 120) * 1_000_000_000),
            open=stop_entry - 0.2,
            high=stop_entry,
            low=stop_px - 0.5,
            close=stop_px - 0.2,
            volume=5_000.0,
        ),
    )
    stopped = run_execution(
        bars=stop_bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=(False, False, False),
        rth=annotate(stop_bars).rth,
        session_dates=annotate(stop_bars).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    if not stopped.trades or stopped.trades[0].reason != "stop":
        _fail("stop must book when the bar trades through the stop")
    if abs(stopped.trades[0].exit_price - stop_px) > 1e-9:
        _fail("stop exit must be the stop price, not the close")
    touch_bars = (
        stop_bars[0],
        stop_bars[1],
        ResearchBar(
            ts_ns=int((start.timestamp() + 120) * 1_000_000_000),
            open=stop_entry - 0.2,
            high=stop_entry,
            low=stop_px,
            close=stop_px + 0.1,
            volume=5_000.0,
        ),
    )
    touched = run_execution(
        bars=touch_bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=(False, False, False),
        rth=annotate(touch_bars).rth,
        session_dates=annotate(touch_bars).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    if not touched.trades or touched.trades[0].reason != "stop":
        _fail("stop must fill on an exact touch")
    if abs(touched.trades[0].exit_price - stop_px) > 1e-9:
        _fail("touch stop must book at the stop price")
    globex_bars = (
        ResearchBar(
            ts_ns=int(datetime(2026, 3, 2, 23, 0, tzinfo=UTC).timestamp() * 1_000_000_000),
            open=5000.0,
            high=5000.5,
            low=4999.5,
            close=5000.0,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int(datetime(2026, 3, 2, 23, 1, tzinfo=UTC).timestamp() * 1_000_000_000),
            open=5000.1,
            high=5000.6,
            low=4999.6,
            close=5000.1,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int(datetime(2026, 3, 2, 23, 2, tzinfo=UTC).timestamp() * 1_000_000_000),
            open=5000.2,
            high=5004.5,
            low=5000.0,
            close=5004.0,
            volume=5_000.0,
        ),
    )
    globex_run = run_execution(
        bars=globex_bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=(False, False, False),
        rth=annotate(globex_bars).rth,
        session_dates=annotate(globex_bars).session_dates,
        session_filter="globex",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    rth_run = run_execution(
        bars=globex_bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=(False, False, False),
        rth=annotate(globex_bars).rth,
        session_dates=annotate(globex_bars).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    if not globex_run.trades:
        _fail("globex filter must still allow overnight entries")
    if rth_run.trades:
        _fail("RTH filter must refuse Globex entries")
    rth_a = ResearchBar(
        ts_ns=int(datetime(2026, 3, 2, 15, 0, tzinfo=UTC).timestamp() * 1_000_000_000),
        open=5000.0,
        high=5000.5,
        low=4999.5,
        close=5000.0,
        volume=5_000.0,
    )
    rth_b = ResearchBar(
        ts_ns=int(datetime(2026, 3, 2, 15, 3, tzinfo=UTC).timestamp() * 1_000_000_000),
        open=5001.0,
        high=5001.5,
        low=5000.5,
        close=5001.0,
        volume=5_000.0,
    )
    hole_tape = prepare_tape(
        "MES",
        (rth_a, rth_b)
        + tuple(
            ResearchBar(
                ts_ns=int((datetime(2026, 3, 2, 15, 4, tzinfo=UTC).timestamp() + index * 60) * 1_000_000_000),
                open=5001.0,
                high=5001.5,
                low=5000.5,
                close=5001.0,
                volume=5_000.0,
            )
            for index in range(240)
        ),
    )
    hole_index = next(i for i, item in enumerate(hole_tape.bars) if item.ts_ns == rth_b.ts_ns)
    if hole_tape.breaks[hole_index] is not True:
        _fail("RTH hole >90s must break")
    body = verify_nt8_rolls()
    mondays = tuple(item for item in NT8_ROLL_DATES if item.weekday() == 0)
    if body["n_monday_rolls"] != len(mondays):
        _fail("Monday roll count drifted")
    if body["friday_2026_06_12_present"] is not True or body["friday_2026_06_12_is_friday"] is not True:
        _fail("Friday roll flags drifted")
    net = tuple(-0.02 if index < 20 else 0.02 for index in range(40))
    market = tuple(
        (0.03 if index % 2 == 0 else 0.001) if index < 20 else (-0.001 if index % 2 == 0 else -0.03)
        for index in range(40)
    )
    snap = regime_robustness(net, market_returns=market)
    if snap.vol_high_sharpe == snap.vol_low_sharpe:
        _fail("high/low vol buckets must split")
    if snap.trend_up_sharpe == snap.trend_down_sharpe and snap.trend_up_sharpe == 0.0:
        _fail("trend buckets must be defined")
    quiet_m = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=0.25)
    model = CostModel()
    contract = spec_for("MES")
    quiet_slip = model.ticks_for_fill(spec=contract, quantity=1.0, market=quiet_m).slippage_ticks
    expected_quiet = 0.10 * (0.25 / contract.tick_size)
    if abs(quiet_slip - expected_quiet) > 0.05:
        _fail("slippage must be coefficient * (true range / tick)")
    _must_raise(
        CostModelError,
        model.ticks_for_fill,
        spec=contract,
        quantity=1.0,
        market=MarketSnapshot(volume=1.0, average_volume=0.0, volatility_price=1.0),
    )
    _must_raise(
        CostModelError,
        model.ticks_for_fill,
        spec=contract,
        quantity=1.0,
        market=MarketSnapshot(volume=-1.0, average_volume=10.0, volatility_price=1.0),
    )
    _must_raise(
        CostModelError,
        model.ticks_for_fill,
        spec=contract,
        quantity=1.0,
        market=MarketSnapshot(volume=1.0, average_volume=10.0, volatility_price=-1.0),
    )
    _must_raise(HoldoutLocked, holdout_ns, 5)
    _must_raise(HoldoutLocked, holdout_ns, 13)
    short_bars = tuple(
        ResearchBar(ts_ns=index + 1, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0) for index in range(3)
    )
    _must_raise(HoldoutLocked, split_holdout, short_bars[:1])
    decreasing = (
        ResearchBar(ts_ns=2, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
        ResearchBar(ts_ns=1, open=1.0, high=1.1, low=0.9, close=1.0, volume=1.0),
    )
    _must_raise(HoldoutLocked, split_holdout, decreasing)
    train, locked, start_ns = split_holdout(short_bars, pinned_start_ns=2)
    if len(train) < 1 or len(locked) < 1:
        _fail("pinned split must keep both sides")
    if train[-1].ts_ns >= start_ns or locked[0].ts_ns < start_ns:
        _fail("split must be strictly < pin vs >= pin")
    _must_raise(HoldoutLocked, assert_not_holdout, 99, holdout_start=10, purpose="gate")
    assert_not_holdout(1, holdout_start=10, purpose="evaluation")
    with TemporaryDirectory() as tmp:
        path = Path(tmp)
        csv = path / "MES" / "1m" / "mes.csv"
        csv.parent.mkdir(parents=True)
        csv.write_bytes(b"x" * (2 * 1024 * 1024 + 17))
        if file_sha256(csv) != hashlib.sha256(csv.read_bytes()).hexdigest():
            _fail("file_sha256 must hash every chunk")
        span_start = datetime(2023, 10, 28, tzinfo=UTC)
        span_end = datetime(2026, 10, 28, tzinfo=UTC)
        n = 40
        step = (span_end - span_start).total_seconds() / float(n - 1)
        bars = tuple(
            ResearchBar(
                ts_ns=int((span_start.timestamp() + float(index) * step) * 1_000_000_000),
                open=5000.0,
                high=5000.5,
                low=4999.5,
                close=5000.0,
                volume=1_000.0,
            )
            for index in range(n)
        )
        tape = LoadedTape(instrument="MES", bar_size="1m", path=csv, bars=bars, holdout_start_ns=P2_HOLDOUT_START_NS)
        _must_raise(HoldoutLocked, seal_holdout, (tape,), report_dir=path / "bad", require_known_files=True)
        sealed = seal_holdout((tape,), report_dir=path / "ok", require_known_files=False)
        if sealed["holdout_start_ns"] != P2_HOLDOUT_START_NS:
            _fail("seal pin drifted")
        loaded = load_seal(path / "ok")
        previous = loaded["previous_seals"]
        if not isinstance(previous, list) or previous[0]["seal_sha256"] != LEGACY_SEAL_SHA256:
            _fail("legacy seal must be recorded on the new seal")
        previous_shas = [item.get("seal_sha256") for item in previous if isinstance(item, dict)]
        if PENDING_COUNTS_SEAL_SHA256 not in previous_shas:
            _fail("pending-counts 23:00Z seal must stay in previous_seals")
        drifted = path / "drift"
        drifted.mkdir()
        (drifted / "phase5_p2_holdout_seal.json").write_text('{"holdout_start_ns": 1}', encoding="utf-8")
        _must_raise(HoldoutLocked, load_seal, drifted)
        empty = path / "empty"
        empty.mkdir()
        _must_raise(HoldoutLocked, load_seal, empty)
        audit = path / "pipe.jsonl"
        registry = TrialRegistry(audit)
        n_obs = 360
        gross = tuple(0.002 for _ in range(n_obs))
        positions = tuple(1.0 for _ in range(n_obs))
        markets = tuple(
            MarketSnapshot(volume=8_000.0, average_volume=10_000.0, volatility_price=1.0) for _ in range(n_obs)
        )
        peers = (tuple(0.001 for _ in range(n_obs)), tuple(-0.001 for _ in range(n_obs)))
        for index, _peer in enumerate(peers):
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
            audit_path=None,
            has_fit_step=False,
            market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n_obs)),
            n_days=80,
        )
        if evaluation.results.n_days != 80:
            _fail("n_days must be the documented session count, not len(net)")
        if evaluation.results.has_fit_step or evaluation.results.wfe.mode != "static_rules":
            _fail("static pipeline must skip CPCV")
        if not evaluation.bootstrap_sharpes:
            _fail("static pipeline must store block-bootstrap sharpes")
        if evaluation.results.embargo_applied is not True:
            _fail("default embargo must be applied on the static path")
        if evaluation.results.n_days == n_obs:
            _fail("n_days must not silently become len(net)")
        zero_embargo = evaluate_candidate(
            agent_id="edge",
            config_id="static-embargo0",
            gross_returns=gross,
            positions=positions,
            markets=markets,
            spec="MES",
            registry=registry,
            peer_net_returns=peers,
            has_fit_step=False,
            embargo=0,
            market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n_obs)),
            n_days=80,
        )
        if zero_embargo.results.embargo_applied is not False:
            _fail("embargo=0 must not claim embargo_applied")
        if "purge_or_embargo_missing" not in zero_embargo.report.reject_reasons:
            _fail("embargo=0 must fail closed")
        fitted = evaluate_candidate(
            agent_id="edge",
            config_id="fit-0",
            gross_returns=gross,
            positions=positions,
            markets=markets,
            spec="MES",
            registry=registry,
            peer_net_returns=peers,
            has_fit_step=True,
            market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n_obs)),
            n_days=80,
        )
        if fitted.results.has_fit_step is not True:
            _fail("fit-step pipeline must keep has_fit_step")
        if access_bars(tape, purpose="gate", pinned_start_ns=P2_HOLDOUT_START_NS)[-1].ts_ns >= P2_HOLDOUT_START_NS:
            _fail("gate purpose must not see holdout")
        if access_bars(tape, purpose="evaluation", pinned_start_ns=P2_HOLDOUT_START_NS)[0].ts_ns < P2_HOLDOUT_START_NS:
            _fail("evaluation purpose must be holdout-only")
        _must_raise(HoldoutLocked, access_bars, tape, purpose="nope", pinned_start_ns=P2_HOLDOUT_START_NS)


def _kill_atr_geometry() -> None:
    """Action-2/3/4/6 locks: ATR points, ES-only July hole, no 1m high-turnover templates."""
    specs = atr_es_specs()
    if len(specs) != 10:
        _fail("ATR ES grid must stay 10 pre-registered configs")
    if any(item.instrument != "ES" for item in specs):
        _fail("ATR grid is ES only")
    templates = {item.template_id for item in specs}
    if "close_reversal" in templates or "volume_imbalance" in templates:
        _fail("no new 1m high-turnover templates")
    if any(item.time_stop_bars != 2000 or not item.session_end_flatten for item in specs):
        _fail("ATR grid must session-flatten with time_stop_bars=2000")
    if ATR_SEAL_NAME == "phase5_p2_es_nq_holdout_seal.json":
        _fail("ATR cycle must not reuse the ES/NQ seal filename")
    gap = next(item for item in specs if item.config_id == "p2a-gap-es")
    if gap.disable_brackets is not True or gap.target_atr is not None:
        _fail("gap family must have no 1m bracket")
    july = int(datetime(2025, 7, 14, 18, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    if in_known_gap("ES", july) is not True or in_known_gap("NQ", july) is not False:
        _fail("July TRAIN hole is ES-specific, not NQ")
    if in_known_gap("MES", july) is not False or in_known_gap("MNQ", july) is not True:
        _fail("July TRAIN hole is MNQ-missing, MES present")
    if points_to_ticks(1.0, tick_size=spec_for("ES").tick_size) != 4:
        _fail("1 point must be 4 ticks on ES")
    if points_to_ticks(1.0, tick_size=spec_for("MES").tick_size) != 4:
        _fail("1 point must be 4 ticks on MES (equal geometry)")
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    atr = 2.0
    target = entry + atr
    bars = (
        ResearchBar(
            ts_ns=int(start.timestamp() * 1_000_000_000),
            open=entry,
            high=entry + 0.25,
            low=entry - 0.25,
            close=entry,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int((start.timestamp() + 60) * 1_000_000_000),
            open=entry + 0.1,
            high=entry + 0.2,
            low=entry - 0.4,
            close=entry + 0.1,
            volume=5_000.0,
        ),
        ResearchBar(
            ts_ns=int((start.timestamp() + 120) * 1_000_000_000),
            open=entry + 0.2,
            high=target + 0.5,
            low=entry,
            close=target + 0.2,
            volume=5_000.0,
        ),
    )
    labels = annotate(bars)
    executed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="ES", target_ticks=16, stop_ticks=8),
        breaks=(False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=2000,
        session_end_flatten=False,
        atr_points=(atr, atr, atr),
        target_atr=1.0,
        stop_atr=1.0,
    )
    if not executed.trades or executed.trades[0].reason != "target":
        _fail("1.0×ATR target must fire before the 16-tick catalog floor")
    if abs(executed.trades[0].exit_price - target) > 1e-9:
        _fail("ATR target must exit at entry + ATR points")
    unbr = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="ES", target_ticks=1, stop_ticks=1),
        breaks=(False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        time_stop_bars=2000,
        session_end_flatten=True,
        disable_brackets=True,
    )
    if not unbr.trades or any(item.reason != "session_end" for item in unbr.trades):
        _fail("disable_brackets must flatten at session end")
    _must_raise(
        ExecutionRefused,
        run_execution,
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=require_geometry(root="ES", target_ticks=1, stop_ticks=1),
        breaks=(False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        target_atr=1.0,
    )
    day = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    rows: list[ResearchBar] = []
    session_index = 0
    while session_index < 4:
        if day.weekday() < 5:
            price = 100.0 + 10.0 * float(session_index)
            for index in range(8):
                ts = day + timedelta(minutes=index)
                rows.append(
                    ResearchBar(
                        ts_ns=int(ts.timestamp() * 1_000_000_000),
                        open=price,
                        high=price + 1.0 + float(session_index),
                        low=price - 0.25,
                        close=price + 0.5,
                        volume=5_000.0,
                    )
                )
            session_index += 1
        day += timedelta(days=1)
    prepared = prepare_tape("ES", tuple(rows))
    series = causal_session_atr(prepared.bars, prepared.session_dates, prepared.rth, n_sessions=14)
    first = prepared.session_dates[0]
    if any(series[index] != 0.0 for index, session in enumerate(prepared.session_dates) if session == first):
        _fail("causal ATR must be 0 on the first completed-prior-less session")


def run() -> None:
    if FILL_POLICY != "trade_through_strict":
        _fail("fill policy drifted")
    bar = ResearchBar(ts_ns=1, open=10.0, high=10.5, low=9.5, close=10.0, volume=100.0)
    if touch_fill(side=1.0, limit=9.5, bar=bar) is not True:
        _fail("touch-fill must remain documented")
    if traded_through(side=1.0, limit=9.5, bar=bar) is not False:
        _fail("touch must not trade through")
    if traded_through(side=1.0, limit=9.6, bar=bar) is not True:
        _fail("low < limit must trade through")
    if traded_through(side=-1.0, limit=10.5, bar=bar) is not False:
        _fail("high == sell limit must not trade through")
    try:
        require_geometry(root="MES", target_ticks=0, stop_ticks=8)
        _fail("target < 1 must refuse")
    except GeometryRefused:
        pass
    geo = require_geometry(root="MES", target_ticks=3, stop_ticks=2)
    if geo.target_ticks != 3:
        _fail("geometry floor must not reject pre-registered 3/2")
    if RTH_OPEN_CLOSE_MIN != 9 * 60 + 31 or RTH_LAST_CLOSE_MIN != 16 * 60:
        _fail("RTH close-time labels drifted")
    et930 = datetime(2026, 3, 2, 14, 30, tzinfo=UTC)
    et931 = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    if is_rth_close(int(et930.timestamp() * 1_000_000_000)):
        _fail("09:30 ET close is not an RTH bar")
    if not is_rth_close(int(et931.timestamp() * 1_000_000_000)):
        _fail("09:31 ET close must be RTH")
    if P2_HOLDOUT_START_UTC != datetime(2026, 1, 28, 23, 0, tzinfo=UTC):
        _fail("holdout pin is not the Globex session boundary")
    if P2_HOLDOUT_START_NS <= 0:
        _fail("holdout ns missing")
    if LEGACY_SEAL_SHA256 != "6e8fa88e3aad048271cb52a63f76cbf4ed8a9261b85b85f03f631b872cf2e51b":
        _fail("legacy seal sha drifted")
    if PENDING_COUNTS_SEAL_SHA256 != "51d55d770aa21fb8f10062c7aab53acebe4866e526eb3419501098bd67172a99":
        _fail("pending-counts seal sha drifted")
    if LIVE_SEAL_SHA256 != "85e4588fde77159315a72bdaa722d6487f93bbad9bf24999311f893950489d40":
        _fail("live holdout seal sha drifted")
    if FRIDAY_ROLL not in NT8_ROLL_SET or FRIDAY_ROLL != date(2026, 6, 12):
        _fail("Friday 2026-06-12 roll missing")
    require_friday_roll()
    if band_for("MNQ") != MNQ_ONE_WAY_USD:
        _fail("MNQ band must be USD")
    if COST_MODEL_VERSION != "1.2.0":
        _fail("cost model version drifted")
    if SLIPPAGE_COEFFICIENT != 0.10 or ETH_SLIPPAGE_COEFFICIENT != 0.10:
        _fail("slippage coefficient retuned")
    if MAX_VOLUME_SLIP_SCALE != 4.0:
        _fail("volume slip cap drifted")
    loaded = load_slippage_calibration()
    if loaded.source != "documented_assumption":
        _fail("slippage source drifted")
    if loaded.eth_coefficient != ETH_SLIPPAGE_COEFFICIENT:
        _fail("ETH coefficient missing from calibration")
    exec_src = inspect.getsource(run_execution)
    if "causal_session_adv" not in exec_src or "session=session" not in exec_src:
        _fail("tape costs must use session-local ADV and session labels")
    rth_bar = ResearchBar(ts_ns=1, open=10.0, high=10.25, low=9.75, close=10.0, volume=10_000.0)
    eth_bar = ResearchBar(ts_ns=2, open=10.0, high=10.25, low=9.75, close=10.0, volume=100.0)
    mixed_bars = tuple([rth_bar] * 21 + [eth_bar])
    mixed_rth = tuple([True] * 21 + [False])
    if abs(causal_session_adv(mixed_bars, mixed_rth, 21) - 100.0) > 1e-9:
        _fail("ETH ADV must ignore RTH volume")
    fill_src = inspect.getsource(CostModel.ticks_for_fill)
    if "eth_slippage_coefficient" not in fill_src or "max_volume_slip_scale" not in fill_src:
        _fail("ticks_for_fill must look up session coefficient and cap inverse volume")
    step_src = inspect.getsource(_Book.step)
    if "opened_flat" not in step_src or "reported" not in step_src:
        _fail("same-bar round trips must remain visible to apply_costs")
    quiet = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=0.25)
    wild = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=5.0)
    model = CostModel()
    contract = spec_for("MES")
    if (
        model.ticks_for_fill(spec=contract, quantity=1.0, market=wild).slippage_ticks
        <= model.ticks_for_fill(spec=contract, quantity=1.0, market=quiet).slippage_ticks
    ):
        _fail("vol term must scale slippage")
    if bar_volatility_price(bar) != 1.0:
        _fail("true range of 10.5-9.5 must be 1.0")
    if STATIC_POSITIVE_SHARE_MIN != 0.60 or STATIC_DECAY_SPEARMAN != -0.50:
        _fail("static A2 constants drifted")
    if not structural_decay((1.0, 0.8, 0.6, 0.4, 0.2, 0.0)):
        _fail("decay must fire on a falling OOS path")
    if structural_decay((0.1, 0.2, 0.15, 0.18, 0.2, 0.22)):
        _fail("stable OOS path must not be decay")
    if structural_decay((1.0, 1.0)):
        pass
    else:
        _fail("too few windows must fail closed")
    if FLOOR_DSR_PROBABILITY_MIN != 0.95 or FLOOR_PBO_HARD_REJECT != 0.50:
        _fail("DSR/PBO floors loosened")
    vx = next(item for item in catalog() if item.config_id == "vx-mes-20")
    if vx.threshold != 0.75 or vx.has_fit_step or vx.session_filter != "rth":
        _fail("catalog VX/session/static flags drifted")
    net = tuple(-0.02 for _ in range(40))
    market = tuple(0.01 if index % 3 else -0.02 for index in range(40))
    snap = regime_robustness(net, market_returns=market)
    if not snap.is_complete():
        _fail("market regimes must be complete on a losing strategy")
    if regime_robustness(net, market_returns=market[:-1]).is_complete():
        _fail("length mismatch must be missing regimes")
    if regime_robustness(net).is_complete():
        _fail("omitted market_returns must be missing regimes")
    wiggly = tuple(0.001 * (1.0 if index % 2 == 0 else -0.4) for index in range(40))
    if not block_bootstrap_sharpes(wiggly, n_paths=8).is_complete():
        _fail("bootstrap must form a distribution")
    if block_bootstrap_sharpes((0.1,)).is_complete():
        _fail("short bootstrap must be missing")
    sessions = (date(2026, 3, 2),) * 3 + (date(2026, 3, 3),) * 3
    rth = (True,) * 6
    bars = tuple(_bar(1_700_000_000_000_000_000 + index * 60_000_000_000, 100.0 + index) for index in range(6))
    planted = rth_session_direction(bars, sessions, rth)
    if 1.0 not in planted:
        _fail("planted session direction missing")
    shuffled = shuffle_signals(planted, seed=3)
    if sorted(shuffled) != sorted(planted):
        _fail("null shuffle must preserve values")
    strong = (0.2, 0.1, 0.3, 0.05, 0.15, 0.12)
    fake_ok = SimpleNamespace(
        report=SimpleNamespace(
            median_oos_after_costs=0.1,
            oos_distribution=SimpleNamespace(pct_positive=positive_share(strong), values=strong),
        )
    )
    if _detected(fake_ok, null_median=None) is not True:  # type: ignore[arg-type]
        _fail("planted edge with positive median and 60%+ windows must detect")
    fake_loss = SimpleNamespace(
        report=SimpleNamespace(
            median_oos_after_costs=-0.1,
            oos_distribution=SimpleNamespace(pct_positive=positive_share(strong), values=strong),
        )
    )
    if _detected(fake_loss, null_median=None) is not False:  # type: ignore[arg-type]
        _fail("negative median must not count as a detected edge")
    if _detected(fake_ok, null_median=0.2) is not False:  # type: ignore[arg-type]
        _fail("planted median must beat the null")
    weak = (-0.1, -0.2, 0.1, -0.05, 0.02, -0.03)
    fake_weak = SimpleNamespace(
        report=SimpleNamespace(
            median_oos_after_costs=0.1,
            oos_distribution=SimpleNamespace(pct_positive=positive_share(weak), values=weak),
        )
    )
    if _detected(fake_weak, null_median=None) is not False:  # type: ignore[arg-type]
        _fail("share below 60% must not detect")
    labels = annotate(bars)
    if len(labels.session_dates) != 6:
        _fail("session annotate length")
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "g.jsonl"
        registry = TrialRegistry(path)
        for index in range(5):
            registry.record(config_id=f"cfg-{index}", agent_id="p2-mut", metrics={"i": index})
        passed, report = passes_validation_gate(_static_bundle(path), registry=registry)
        if not passed:
            _fail(f"static A2 bundle must pass, got {report.reject_reasons}")
        decayed, decay_report = passes_validation_gate(
            _static_bundle(
                path,
                wfe=WFESnapshot(
                    wfe=math.nan,
                    mean_is_sharpe=-1.2,
                    mean_oos_sharpe=0.4,
                    n_windows=6,
                    mode="static_rules",
                    parameter_stability=0.0,
                ),
            ),
            registry=registry,
        )
        if decayed or "static_structural_decay" not in decay_report.reject_reasons:
            _fail("decay must reject static rules")
        weak_dsr, dsr_report = passes_validation_gate(
            _static_bundle(
                path,
                dsr=DSRSnapshot(
                    probability=0.50,
                    observed_sr=0.05,
                    expected_max_sr=0.08,
                    sr_standard_error=0.04,
                    n_trials=5,
                    n_observations=300,
                    skew=0.0,
                    kurtosis=3.0,
                    formulation="bailey_lopez_de_prado_2014",
                ),
            ),
            registry=registry,
        )
        if weak_dsr or "dsr_below_threshold" not in dsr_report.reject_reasons:
            _fail("DSR floor must still reject static rules")
        zero, zero_report = passes_validation_gate(
            _static_bundle(path, median_oos_after_costs=0.0),
            registry=registry,
        )
        if zero or "static_median_oos_not_positive" not in zero_report.reject_reasons:
            _fail("A2 median OOS must be strictly greater than 0")
    roll_dates = (date(2026, 6, 11), date(2026, 6, 11), date(2026, 6, 12), date(2026, 6, 12))
    raw = (
        _bar(1, 100.0),
        _bar(2, 101.0),
        _bar(3, 200.0),
        _bar(4, 201.0),
    )
    adjusted = back_adjust(raw, roll_dates)
    if adjusted[-1].close != raw[-1].close:
        _fail("latest contract must stay unadjusted")
    if adjusted[0].close == raw[0].close:
        _fail("earlier bars must shift across the roll")
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    exec_bars = tuple(
        ResearchBar(
            ts_ns=int((start.timestamp() + index * 60) * 1_000_000_000),
            open=5000.0 + index * 0.05,
            high=5000.5 + index * 0.05,
            low=4999.5 + index * 0.05,
            close=5000.0 + index * 0.05,
            volume=5_000.0,
        )
        for index in range(8)
    )
    executed = run_execution(
        bars=exec_bars,
        signals=(1.0,) + (0.0,) * 7,
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=tuple(False for _ in exec_bars),
        rth=annotate(exec_bars).rth,
        session_dates=annotate(exec_bars).session_dates,
        time_stop_bars=2,
        session_end_flatten=False,
    )
    if not executed.trades or executed.trades[0].reason != "time_stop":
        _fail("time-stop must close at bar close")
    if back_adjust((), ()) != ():
        _fail("empty back-adjust must be empty")
    try:
        back_adjust(raw, roll_dates[:-1])
        _fail("misaligned back-adjust must refuse")
    except ValueError:
        pass
    if traded_through(side=0.0, limit=9.6, bar=bar) or touch_fill(side=0.0, limit=9.6, bar=bar):
        _fail("flat side must not fill")
    if band_for("ES")[0] <= 0.0 or band_for("MES")[0] <= 0.0 or band_for("NQ")[0] <= 0.0:
        _fail("USD bands must be positive")
    _must_raise(FillRefused, trade_through_fill, side=1.0, limit=9.6, bar=bar, average_volume=0.0)
    _must_raise(FillRefused, fill_probability, side=1.0, limit=9.6, bar=bar, average_volume=0.0)
    if fill_probability(side=0.0, limit=9.6, bar=bar, average_volume=50.0) != 0.0:
        _fail("flat fill probability must be 0")
    if trade_through_fill(side=1.0, limit=9.6, bar=bar, average_volume=50.0) is not True:
        _fail("volume-ok trade-through must fill")
    _must_raise(
        ExecutionRefused,
        run_execution,
        bars=exec_bars,
        signals=(1.0,),
        geometry=geo,
        breaks=(False,),
        rth=(True,),
        session_dates=annotate(exec_bars).session_dates,
    )
    _must_raise(
        ExecutionRefused,
        run_execution,
        bars=exec_bars[:1],
        signals=(1.0,),
        geometry=geo,
        breaks=(False,),
        rth=(True,),
        session_dates=annotate(exec_bars[:1]).session_dates,
        time_stop_bars=0,
    )
    _must_raise(GeometryRefused, require_geometry, root="MES", target_ticks=1, stop_ticks=0)
    _must_raise(ValueError, band_for, "CL")
    _must_raise(HoldoutLocked, holdout_ns, 1)
    _must_raise(HoldoutLocked, holdout_ns, 99)
    _must_raise(HoldoutLocked, load_seal, Path("/tmp/p2-mut-missing-seal-dir"))
    _must_raise(CostModelError, CostModel, slippage_coefficient=-0.1)
    _must_raise(
        CostModelError,
        CostModel().ticks_for_fill,
        spec=contract,
        quantity=0.0,
        market=quiet,
    )
    _must_raise(
        CostModelError,
        apply_costs,
        gross_returns=(0.1,),
        positions=(1.0, 0.0),
        equity=100_000.0,
        spec="MES",
        markets=(quiet,),
    )
    _must_raise(
        CostModelError,
        apply_costs,
        gross_returns=(0.1,),
        positions=(1.0,),
        equity=0.0,
        spec="MES",
        markets=(quiet,),
    )
    if floors_for("MES") != (16, 8) or floors_for("ES") != (8, 4):
        _fail("catalog default geometry drifted")
    if floors_for("NQ") != (8, 4) or floors_for("MNQ") != (16, 8):
        _fail("NQ/MNQ catalog geometry drifted")
    _must_raise(
        FillRefused, trade_through_fill, side=1.0, limit=9.6, bar=bar, average_volume=50.0, volume_multiple=-0.1
    )
    tape = LoadedTape(instrument="MES", bar_size="1m", path=Path("x.csv"), bars=exec_bars)
    _must_raise(HoldoutLocked, access_bars, tape, purpose="nope")
    if not structural_decay(()):
        _fail("empty OOS must fail-closed decay")
    if math.isfinite(positive_share(())):
        _fail("empty positive_share must be nan")
    _kill_deeper()
    _kill_remaining_survivors()
    _kill_atr_geometry()
    code = pytest.main(
        [
            "-q",
            "--tb=no",
            "--timeout=20",
            "tests/research/test_phase5_p2_fixes.py",
            "tests/research/test_gate.py",
            "tests/research/test_phase5_p2_attacks.py::test_stop_touch_and_gap_through_book_conservative_exits",
            "tests/research/test_phase5_p2_attacks.py::test_unbalanced_hitrate_counts_only_winning_trades",
            "tests/research/test_phase5_p2_attacks.py::test_n_days_sizes_from_session_count_not_bar_count",
            "tests/research/test_phase5_p2_attacks.py::test_static_embargo_zero_is_not_claimed_applied",
            "tests/research/test_phase5_p2_attacks.py::test_locked_purposes_cannot_read_bars_at_or_after_holdout_pin",
            "tests/research/test_phase5_p2_attacks.py::test_mnq_usd_band_is_not_the_legacy_tick_interval",
            "tests/research/test_phase5_p2_attacks.py::test_regime_labels_are_causal_in_past_windows",
            "tests/research/test_phase5_p2_attacks.py::test_overnight_globex_gap_is_not_an_rth_hole",
            "tests/research/test_phase5_p2_attacks.py::test_first_roll_session_bar_breaks_later_bars_do_not",
            "tests/research/test_phase5_p2_attacks.py::test_holdout_pin_on_last_timestamp_is_refused",
            "tests/research/test_phase5_p2_attacks.py::test_flatten_off_does_not_emit_session_end",
        ]
    )
    if code != 0:
        raise AssertionError(f"pytest kill battery exit {code}")


if __name__ == "__main__":
    run()
