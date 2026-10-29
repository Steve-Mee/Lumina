"""Fail-closed kill battery for P2 artefact-fix modules."""

from __future__ import annotations

import hashlib
import inspect
import math
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

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
    band_for,
    report_band,
)
from lumina_research.cycles.data import LoadedTape, ResearchBar
from lumina_research.cycles.diagnostics import from_trades
from lumina_research.cycles.execution import ClosedTrade, ExecutionRefused, bar_volatility_price, run_execution
from lumina_research.cycles.fills import (
    FILL_POLICY,
    FillRefused,
    fill_probability,
    touch_fill,
    trade_through_fill,
    traded_through,
)
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
from lumina_research.cycles.positive_control import execute_control, rth_session_direction, shuffle_signals
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.cycles.roll_verify import FRIDAY_ROLL, require_friday_roll, verify_nt8_rolls
from lumina_research.cycles.rolls import NT8_ROLL_DATES, NT8_ROLL_SET
from lumina_research.cycles.seal import LEGACY_SEAL_SHA256, file_sha256, load_seal, seal_holdout
from lumina_research.cycles.sessions import (
    INTRASESSION_HOLE_NS,
    RTH_LAST_CLOSE_MIN,
    RTH_OPEN_CLOSE_MIN,
    annotate,
    is_rth_close,
)
from lumina_research.cycles.slippage_calibration import (
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
    CostModel,
    CostModelError,
    MarketSnapshot,
    apply_costs,
)
from lumina_research.validation.gate import passes_validation_gate
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation.regimes import regime_robustness
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


def _kill_deeper() -> None:
    """Behavioral assertions aimed at the remaining mutation sites."""
    if ES_NQ_ONE_WAY != (0.5, 1.5) or MES_MNQ_ONE_WAY != (1.0, 2.5):
        _fail("informational tick conversions drifted")
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
    if "target_ticks=8" not in src or "stop_ticks=8" not in src:
        _fail("control geometry must stay 8/8")
    if "time_stop_bars=16" not in src:
        _fail("control time-stop must stay 16")
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
    if FRIDAY_ROLL not in NT8_ROLL_SET or FRIDAY_ROLL != date(2026, 6, 12):
        _fail("Friday 2026-06-12 roll missing")
    require_friday_roll()
    if band_for("MNQ") != MNQ_ONE_WAY_USD:
        _fail("MNQ band must be USD")
    if COST_MODEL_VERSION != "1.1.0":
        _fail("cost model version drifted")
    if SLIPPAGE_COEFFICIENT != 0.10:
        _fail("slippage coefficient retuned")
    loaded = load_slippage_calibration()
    if loaded.source != "documented_assumption":
        _fail("slippage source drifted")
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
    code = pytest.main(
        [
            "-q",
            "--tb=no",
            "--timeout=20",
            "tests/research/test_phase5_p2_fixes.py",
            "tests/research/test_gate.py",
        ]
    )
    if code != 0:
        raise AssertionError(f"pytest kill battery exit {code}")


if __name__ == "__main__":
    run()
