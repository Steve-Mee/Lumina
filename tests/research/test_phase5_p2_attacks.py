"""Attack tests for P2 artefact fixes. Each case fails if the requirement is broken."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.cycles.adjust import back_adjust
from lumina_research.cycles.cost_bands import MES_MNQ_ONE_WAY, MNQ_ONE_WAY_USD, band_for, report_band
from lumina_research.cycles.daily import daily_market_returns
from lumina_research.cycles.data import LoadedTape, ResearchBar
from lumina_research.cycles.diagnostics import from_trades
from lumina_research.cycles.execution import ClosedTrade, run_execution
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import P2_HOLDOUT_START_NS, HoldoutLocked, access_bars, split_holdout
from lumina_research.cycles.p2_cycle import prepare_for_purpose, session_day_count
from lumina_research.cycles.positive_control import PositiveControlFailed, run_controls, shuffle_signals
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.cycles.runner import run_research_cycles
from lumina_research.cycles import runner as runner_mod
from lumina_research.cycles.sessions import annotate
from lumina_research.cycles.strategies import simulate_full
from lumina_research.cycles.wf_sizes import walk_forward_sizes
from lumina_research.validation.cost_model import MarketSnapshot, apply_costs
from lumina_research.validation.pipeline import evaluate_candidate
from lumina_research.validation import regimes as regimes_mod
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import RegimeSnapshot
from tests.research.test_phase5_p2_fixes import _bar, _control_tape, _rth_minutes

UTC = timezone.utc


def _span_across_pin(n_train: int = 8, n_hold: int = 4) -> tuple[ResearchBar, ...]:
    pin = datetime(2026, 1, 28, 23, 0, tzinfo=UTC)
    rows: list[ResearchBar] = []
    for index in range(n_train, 0, -1):
        ts = pin - timedelta(minutes=index)
        rows.append(_bar(ts, open_=5000.0, high=5000.5, low=4999.5, close=5000.0))
    for index in range(n_hold):
        ts = pin + timedelta(minutes=index)
        rows.append(_bar(ts, open_=5001.0, high=5001.5, low=5000.5, close=5001.0))
    return tuple(rows)


@pytest.mark.unit
def test_stop_touch_and_gap_through_book_conservative_exits() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    stop = entry - 8 * 0.25
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    touch = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry - 0.1, high=entry, low=entry - 0.1, close=entry - 0.1),
        _bar(start + timedelta(minutes=2), open_=entry - 0.2, high=entry, low=stop, close=stop + 0.1),
    )
    touched = run_execution(
        bars=touch,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=annotate(touch).rth,
        session_dates=annotate(touch).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert touched.trades[0].reason == "stop"
    assert touched.trades[0].exit_price == pytest.approx(stop)
    gapped = (
        touch[0],
        touch[1],
        _bar(start + timedelta(minutes=2), open_=stop - 1.0, high=stop - 0.5, low=stop - 1.2, close=stop - 0.8),
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
    assert gap_exec.trades[0].reason == "stop"
    assert gap_exec.trades[0].exit_price == pytest.approx(stop - 1.0)


@pytest.mark.unit
def test_target_touch_does_not_fill_trade_through_does() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    target = entry + 16 * 0.25
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    touch = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry + 0.1, high=entry + 0.2, low=entry - 0.4, close=entry + 0.1),
        _bar(start + timedelta(minutes=2), open_=entry + 0.2, high=target, low=entry, close=target - 0.1),
    )
    missed = run_execution(
        bars=touch,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=annotate(touch).rth,
        session_dates=annotate(touch).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert all(item.reason != "target" for item in missed.trades)
    through = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry + 0.1, high=entry + 0.2, low=entry - 0.4, close=entry + 0.1),
        _bar(start + timedelta(minutes=2), open_=entry + 0.2, high=target + 0.5, low=entry, close=target + 0.1),
    )
    filled = run_execution(
        bars=through,
        signals=(1.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False, False, False),
        rth=annotate(through).rth,
        session_dates=annotate(through).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=False,
    )
    assert filled.trades[0].reason == "target"
    assert filled.trades[0].exit_price == pytest.approx(target)


@pytest.mark.unit
def test_mean_reversion_does_not_look_ahead_to_future_bars() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = _rth_minutes(start, 241, 5000.0, step=0.05)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    base = simulate_full(
        family="mean_reversion",
        bars=bars,
        geometry=geo,
        lookback=10,
        threshold=1.5,
        mode="fade",
        session_end_flatten=False,
    )
    spiked = list(bars)
    last = bars[-1]
    spiked[-1] = ResearchBar(
        ts_ns=last.ts_ns,
        open=last.open,
        high=last.high + 80.0,
        low=last.low,
        close=last.close + 80.0,
        volume=last.volume,
    )
    mutated = simulate_full(
        family="mean_reversion",
        bars=tuple(spiked),
        geometry=geo,
        lookback=10,
        threshold=1.5,
        mode="fade",
        session_end_flatten=False,
    )
    assert base.positions[:-2] == mutated.positions[:-2]


@pytest.mark.unit
def test_regime_labels_are_causal_in_past_windows() -> None:
    market = tuple(0.01 if index % 3 else -0.02 for index in range(40))
    leaked = market[:-1] + (9.0,)
    vol_a = regimes_mod._rolling_vol(market, 20)
    vol_b = regimes_mod._rolling_vol(leaked, 20)
    trend_a = regimes_mod._rolling_trend(market, 20)
    trend_b = regimes_mod._rolling_trend(leaked, 20)
    assert vol_a[:-1] == vol_b[:-1]
    assert trend_a[:-1] == trend_b[:-1]
    assert vol_a[-1] != vol_b[-1]


@pytest.mark.unit
def test_pnl_uses_unadjusted_prices_indicators_use_adjusted() -> None:
    pre = _rth_minutes(datetime(2026, 6, 11, 14, 31, tzinfo=UTC), 20, 5000.0)
    roll = _bar(datetime(2026, 6, 11, 22, 1, tzinfo=UTC), open_=5300.0, high=5301.0, low=5299.0, close=5300.0)
    after = _rth_minutes(datetime(2026, 6, 12, 14, 31, tzinfo=UTC), 230, 5300.0)
    bars = pre + (roll,) + after
    labels = annotate(bars)
    adjusted = back_adjust(bars, labels.session_dates)
    assert adjusted[0].close != pytest.approx(bars[0].close)
    assert adjusted[-1].close == pytest.approx(bars[-1].close)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    executed = run_execution(
        bars=pre[:6],
        signals=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        geometry=geo,
        breaks=(False,) * 6,
        rth=annotate(pre[:6]).rth,
        session_dates=annotate(pre[:6]).session_dates,
        session_filter="rth",
        time_stop_bars=16,
        session_end_flatten=True,
    )
    assert executed.trades
    assert executed.trades[0].entry_price == pytest.approx(pre[0].close)
    assert executed.trades[0].entry_price != pytest.approx(adjusted[0].close)


@pytest.mark.unit
def test_locked_purposes_cannot_read_bars_at_or_after_holdout_pin() -> None:
    bars = _span_across_pin()
    path = Path("mes.csv")
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=path,
        bars=bars,
        holdout_start_ns=P2_HOLDOUT_START_NS,
    )
    for purpose in ("selection", "template_selection", "tuning", "calibration", "gate", "first_cycle"):
        train = access_bars(tape, purpose=purpose, pinned_start_ns=P2_HOLDOUT_START_NS)
        assert train
        assert all(item.ts_ns < P2_HOLDOUT_START_NS for item in train)
        with pytest.raises(HoldoutLocked):
            access_bars(
                LoadedTape(
                    instrument="MES",
                    bar_size="1m",
                    path=path,
                    bars=tuple(item for item in bars if item.ts_ns >= P2_HOLDOUT_START_NS),
                    holdout_start_ns=P2_HOLDOUT_START_NS,
                ),
                purpose=purpose,
                pinned_start_ns=P2_HOLDOUT_START_NS,
            )


@pytest.mark.unit
def test_prepare_for_purpose_gate_drops_post_pin_bars() -> None:
    body = _span_across_pin(n_train=300, n_hold=0)
    late = _rth_minutes(datetime(2026, 1, 29, 14, 31, tzinfo=UTC), 50, 5001.0)
    bars = body + late
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=Path("mes.csv"),
        bars=bars,
        holdout_start_ns=P2_HOLDOUT_START_NS,
    )
    prepared = prepare_for_purpose(tape, purpose="gate")
    assert prepared.bars
    assert all(item.ts_ns < P2_HOLDOUT_START_NS for item in prepared.bars)
    assert any(item.ts_ns >= P2_HOLDOUT_START_NS for item in late)


@pytest.mark.unit
def test_mnq_usd_band_is_not_the_legacy_tick_interval() -> None:
    assert band_for("MNQ") == MNQ_ONE_WAY_USD
    assert band_for("MNQ") != MES_MNQ_ONE_WAY
    band = report_band("MNQ")
    assert band.band_min_usd == MNQ_ONE_WAY_USD[0]
    assert band.modeled_one_way_usd > 1.0
    assert band.modeled_one_way_bp > 0.0
    assert band.band_min_usd == pytest.approx(1.20)
    assert band.band_max_usd == pytest.approx(5.00)


@pytest.mark.unit
def test_flat_tape_positive_control_fails_closed(tmp_path: Path) -> None:
    rows: list[ResearchBar] = []
    day = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    session_index = 0
    while session_index < 22:
        if day.weekday() < 5:
            for index in range(24):
                ts = day + timedelta(minutes=index)
                rows.append(_bar(ts, open_=5000.0, high=5000.25, low=4999.75, close=5000.0, volume=8_000.0))
            session_index += 1
        day += timedelta(days=1)
    prepared = prepare_tape("MES", tuple(rows))
    market = daily_market_returns(prepared.bars, prepared.session_dates)
    with pytest.raises(PositiveControlFailed):
        run_controls(
            prepared={"MES": prepared},
            registry=TrialRegistry(tmp_path / "flat.jsonl"),
            audit_path=tmp_path / "flat.jsonl",
            is_size=6,
            oos_size=2,
            market_returns=market,
            n_days=22,
        )


@pytest.mark.unit
def test_identity_null_is_not_accepted_as_an_edge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _control_tape()
    market = daily_market_returns(prepared.bars, prepared.session_dates)

    def _identity(signals: tuple[float, ...] | list[float], *, seed: int) -> tuple[float, ...]:
        del seed
        return tuple(float(item) for item in signals)

    monkeypatch.setattr("lumina_research.cycles.positive_control.shuffle_signals", _identity)
    with pytest.raises(PositiveControlFailed, match="null control|not detected"):
        run_controls(
            prepared={"MES": prepared},
            registry=TrialRegistry(tmp_path / "null.jsonl"),
            audit_path=tmp_path / "null.jsonl",
            is_size=6,
            oos_size=2,
            market_returns=market,
            n_days=22,
        )


@pytest.mark.unit
def test_runner_stop_reason_is_positive_control_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    start = datetime(2025, 1, 6, 15, 0, tzinfo=UTC)
    bars = _rth_minutes(start, 300, 5000.0)
    lines = ["timestamp,open,high,low,close,volume"]
    for bar in bars:
        stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=UTC).isoformat()
        lines.append(f"{stamp},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    payload = "\n".join(lines) + "\n"
    (tmp_path / "data" / "research" / "MES" / "1m").mkdir(parents=True)
    (tmp_path / "data" / "research" / "MNQ" / "1m").mkdir(parents=True)
    (tmp_path / "data" / "research" / "MES" / "1m" / "mes.csv").write_text(payload, encoding="utf-8")
    (tmp_path / "data" / "research" / "MNQ" / "1m" / "mnq.csv").write_text(payload, encoding="utf-8")

    def _raise(**kwargs: object) -> None:
        del kwargs
        raise PositiveControlFailed("planted edge missed")

    monkeypatch.setattr(runner_mod, "_is_real_p2", lambda _status: True)
    monkeypatch.setattr(runner_mod, "DAILY_RESAMPLE_MIN_BARS", 1)
    monkeypatch.setattr(runner_mod, "run_controls", _raise)
    monkeypatch.setattr(
        runner_mod,
        "seal_holdout",
        lambda *_args, **_kwargs: {"seal_sha256": "abc", "holdout_start_ns": P2_HOLDOUT_START_NS},
    )
    monkeypatch.setattr(runner_mod, "load_seal", lambda _path: {"holdout_start_ns": P2_HOLDOUT_START_NS})
    monkeypatch.setattr(
        runner_mod,
        "prepare_for_purpose",
        lambda tape, purpose: prepare_tape(tape.instrument, bars),
    )
    monkeypatch.setattr(runner_mod, "pin_tape", lambda tape: tape)
    monkeypatch.setattr(runner_mod, "write_data_manifest", lambda *_args, **_kwargs: None)
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
        specs=first_cycle_specs()[:1],
    )
    assert result.report.stopped is True
    assert result.report.stop_reason == "positive_control_failed"
    assert result.report.n_tested == 0
    assert result.report.planted_detected is False


@pytest.mark.unit
def test_static_embargo_zero_is_not_claimed_applied(tmp_path: Path) -> None:
    audit = tmp_path / "embargo.jsonl"
    registry = TrialRegistry(audit)
    n = 360
    gross = tuple(0.002 for _ in range(n))
    positions = tuple(1.0 for _ in range(n))
    markets = tuple(MarketSnapshot(volume=8_000.0, average_volume=10_000.0, volatility_price=1.0) for _ in range(n))
    peers = (tuple(0.001 for _ in range(n)), tuple(-0.001 for _ in range(n)))
    for index, _peer in enumerate(peers):
        registry.record(config_id=f"peer-{index}", agent_id="edge", metrics={"i": index})
    zero = evaluate_candidate(
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
        embargo=0,
        market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n)),
        n_days=80,
    )
    assert zero.results.embargo_applied is False
    assert zero.passed is False
    assert "purge_or_embargo_missing" in zero.report.reject_reasons
    defaulted = evaluate_candidate(
        agent_id="edge",
        config_id="static-1",
        gross_returns=gross,
        positions=positions,
        markets=markets,
        spec="MES",
        registry=registry,
        peer_net_returns=peers,
        has_fit_step=False,
        market_returns=tuple(0.0004 if index % 2 == 0 else -0.0003 for index in range(n)),
        n_days=80,
    )
    assert defaulted.results.embargo_applied is True
    assert defaulted.results.n_days == 80
    assert defaulted.results.n_days != n
    assert not defaulted.bootstrap_sharpes or defaulted.results.has_fit_step is False


@pytest.mark.unit
def test_n_days_sizes_from_session_count_not_bar_count() -> None:
    is_size, oos_size, formed = walk_forward_sizes(43)
    assert formed >= 6
    assert oos_size == max(2, (43 - 40) // 8)
    assert is_size != 43
    bars = _rth_minutes(datetime(2026, 3, 2, 14, 31, tzinfo=UTC), 50, 5000.0)
    bars += _rth_minutes(datetime(2026, 3, 3, 14, 31, tzinfo=UTC), 50, 5000.0)
    bars += _rth_minutes(datetime(2026, 3, 4, 14, 31, tzinfo=UTC), 50, 5000.0)
    prepared = prepare_tape("MES", bars)
    assert session_day_count({"MES": prepared}) == 3
    assert session_day_count({"MES": prepared}) != len(prepared.bars)


@pytest.mark.unit
def test_unbalanced_hitrate_counts_only_winning_trades() -> None:
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    trades = (
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=5004.0, pnl_ticks=16.0, reason="target"),
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=5004.0, pnl_ticks=16.0, reason="target"),
        ClosedTrade(side=1.0, entry_price=5000.0, exit_price=4998.0, pnl_ticks=-8.0, reason="stop"),
    )
    costed = apply_costs(
        gross_returns=(0.01, 0.01, -0.002),
        positions=(1.0, 1.0, 0.0),
        equity=100_000.0,
        spec="MES",
        markets=tuple(MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0) for _ in range(3)),
    )
    diag = from_trades(
        trades=trades,
        geometry=geo,
        costed=costed,
        is_sharpes=(0.4,),
        oos_sharpes=(0.2,),
        regimes=RegimeSnapshot(0.1, 0.2, 0.3, -0.1, 0.4),
        n_trials=5,
        n_days=10,
        pct_positive_oos=0.5,
    )
    assert diag.hitrate == pytest.approx(2.0 / 3.0)


@pytest.mark.unit
def test_research_source_has_no_fixed_volatility_price_two() -> None:
    root = Path("lumina_research")
    hits: list[str] = []
    pattern = re.compile(r"volatility_price\s*=\s*2(?:\.0)?\b")
    for path in root.rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                continue
            if "never" in stripped.lower() or ("fixed" in stripped.lower() and "2.0" in stripped):
                continue
            if pattern.search(line) and "MarketSnapshot" in line:
                hits.append(f"{path.as_posix()}:{lineno}:{stripped}")
    assert hits == []


@pytest.mark.unit
def test_overnight_globex_gap_is_not_an_rth_hole() -> None:
    globex = datetime(2026, 3, 2, 13, 0, tzinfo=UTC)
    rth = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = (
        _bar(globex, open_=5000.0, high=5000.5, low=4999.5, close=5000.0),
        _bar(rth, open_=5001.0, high=5001.5, low=5000.5, close=5001.0),
        _bar(rth + timedelta(minutes=1), open_=5001.0, high=5001.5, low=5000.5, close=5001.0),
    )
    tape = prepare_tape("MES", bars)
    assert tape.breaks[1] is False


@pytest.mark.unit
def test_first_roll_session_bar_breaks_later_bars_do_not() -> None:
    start = datetime(2026, 6, 12, 14, 31, tzinfo=UTC)
    bars = tuple(
        _bar(start + timedelta(minutes=index), open_=5000.0, high=5000.5, low=4999.5, close=5000.0)
        for index in range(4)
    )
    tape = prepare_tape("MES", bars)
    assert tape.breaks[0] is True
    assert tape.breaks[1] is False
    assert tape.breaks[2] is False


@pytest.mark.unit
def test_holdout_pin_on_last_timestamp_is_refused() -> None:
    bars = tuple(
        _bar(datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index), open_=1.0, high=1.1, low=0.9, close=1.0)
        for index in range(5)
    )
    with pytest.raises(HoldoutLocked):
        split_holdout(bars, pinned_start_ns=int(bars[-1].ts_ns))
    messy = (
        _bar(datetime(2026, 1, 1, 0, 0, tzinfo=UTC), open_=1.0, high=1.1, low=0.9, close=1.0),
        _bar(datetime(2026, 1, 1, 0, 2, tzinfo=UTC), open_=1.0, high=1.1, low=0.9, close=1.0),
        _bar(datetime(2026, 1, 1, 0, 1, tzinfo=UTC), open_=1.0, high=1.1, low=0.9, close=1.0),
        _bar(datetime(2026, 1, 1, 0, 3, tzinfo=UTC), open_=1.0, high=1.1, low=0.9, close=1.0),
    )
    with pytest.raises(HoldoutLocked):
        split_holdout(messy, pinned_start_ns=int(messy[1].ts_ns) - 30_000_000_000)


@pytest.mark.unit
def test_flatten_off_does_not_emit_session_end() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = _rth_minutes(start, 8, 5000.0, step=0.05)
    executed = run_execution(
        bars=bars,
        signals=(1.0,) + (0.0,) * 7,
        geometry=require_geometry(root="MES", target_ticks=16, stop_ticks=8),
        breaks=tuple(False for _ in bars),
        rth=annotate(bars).rth,
        session_dates=annotate(bars).session_dates,
        time_stop_bars=100,
        session_end_flatten=False,
    )
    assert all(item.reason != "session_end" for item in executed.trades)


@pytest.mark.unit
def test_shuffle_signals_is_not_identity_on_mixed_tape() -> None:
    planted = tuple(1.0 if index % 3 == 0 else (-1.0 if index % 3 == 1 else 0.0) for index in range(30))
    shuffled_rows = tuple(shuffle_signals(planted, seed=seed) for seed in range(20))
    assert all(sorted(item) == sorted(planted) for item in shuffled_rows)
    assert any(item != planted for item in shuffled_rows)
