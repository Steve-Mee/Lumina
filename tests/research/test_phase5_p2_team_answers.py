"""Onderzoeksteam 17:34 answers to the nine PR #72 questions."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.cycles.atr_cycle import DSR_ONLY_KILLS, atr_es_specs
from lumina_research.cycles.daily import daily_market_returns
from lumina_research.cycles.diagnostics import UNBRACKET_HORIZONS, from_trades
from lumina_research.cycles.execution import ClosedTrade, run_execution
from lumina_research.cycles.geometry import family_break_even_win_rate, require_geometry
from lumina_research.cycles.nq_lock import NQTemplatesClosed, assert_nq_templates_closed
from lumina_research.cycles.null_model import (
    NULL_CALIBRATED_POSITIVE_SHARE,
    classify_null_a2,
    fail_closed_a2_cap,
    fail_closed_hit_count,
    null_seed_is_false_edge,
)
from lumina_research.cycles.positive_control import (
    BREAKOUT_MIDPOINT_ATR,
    FADE_MIDPOINT_ATR,
    required_midpoint_controls,
    run_controls,
)
from lumina_research.cycles.sessions import annotate
from lumina_research.validation.cost_model import MarketSnapshot, apply_costs
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import RegimeSnapshot
from tests.research.test_phase5_p2_fixes import _bar, _control_tape

UTC = timezone.utc
AUDIT_JSON = Path("experiments/reports/phase5_p2_multiseed_null_audit.json")


@pytest.mark.unit
def test_null_bar_is_four_of_thirty_two_not_majority() -> None:
    assert fail_closed_a2_cap(32) == 3
    assert fail_closed_hit_count(32) == 4
    assert classify_null_a2(0, 32).status == "reliable"
    assert classify_null_a2(3, 32).exact == "3/32"
    assert classify_null_a2(3, 32).within_ten_pct is True
    mes_atr = classify_null_a2(4, 32)
    assert mes_atr.status == "unreliable"
    assert mes_atr.reliable is False
    assert mes_atr.borderline is False
    assert mes_atr.exact == "4/32"
    leaked = classify_null_a2(5, 32)
    assert leaked.status == "unreliable"
    assert leaked.reliable is False
    assert leaked.exact == "5/32"


@pytest.mark.unit
def test_action1_unclipped_null_a2_and_calibrated_edge_from_frozen_json() -> None:
    payload = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
    expected_a2 = {"MES": 6, "MNQ": 10, "ES": 5, "NQ": 8}
    expected_edge = {"MES": 0, "MNQ": 1, "ES": 0, "NQ": 0}
    assert NULL_CALIBRATED_POSITIVE_SHARE == 0.875
    for row in payload["roots"]:
        root = str(row["root"])
        n_a2 = int(row["n_a2"])
        assert n_a2 == expected_a2[root]
        a2_class = classify_null_a2(n_a2, 32)
        assert a2_class.exact == f"{n_a2}/32"
        assert a2_class.status == "unreliable"
        n_edge = sum(
            1
            for seed in row["drift_seeds"]
            if null_seed_is_false_edge(detected=bool(seed["detected"]), pct_positive=float(seed["pct_positive"]))
        )
        assert n_edge == expected_edge[root]
        edge_class = classify_null_a2(n_edge, 32)
        assert edge_class.status == "reliable"
        assert edge_class.exact == f"{n_edge}/32"


@pytest.mark.unit
def test_atr_d13_counts_from_end_report_are_es_pass_mes_fail() -> None:
    es = classify_null_a2(1, 32)
    mes = classify_null_a2(4, 32)
    assert es.status == "reliable"
    assert es.exact == "1/32"
    assert mes.status == "unreliable"
    assert mes.reliable is False
    assert mes.exact == "4/32"


@pytest.mark.unit
def test_positive_control_passes_under_pre_registered_midpoints(tmp_path: Path) -> None:
    prepared = _control_tape()
    market = daily_market_returns(prepared.bars, prepared.session_dates)
    for name, target, stop in required_midpoint_controls():
        report = run_controls(
            prepared={"MES": prepared},
            registry=TrialRegistry(tmp_path / f"midpoint-{name}.jsonl"),
            audit_path=tmp_path / f"midpoint-{name}.jsonl",
            is_size=6,
            oos_size=2,
            market_returns=market,
            n_days=22,
            geometry_mode="atr",
            target_atr=target,
            stop_atr=stop,
            null_seeds=(20261029, 20261030, 20261031, 20261032),
            block_seeds=(),
        )
        assert report.positive.detected is True, name
        assert report.accepted is True, name
        assert report.null_audit is not None
        assert report.null_audit.exact_edge == f"{report.null_audit.n_edge}/4"
        assert report.null_audit.exact_a2 == f"{report.null_audit.n_a2}/4"


@pytest.mark.unit
def test_midpoints_and_positive_control_params_are_locked() -> None:
    assert FADE_MIDPOINT_ATR == (1.0, 1.2)
    assert BREAKOUT_MIDPOINT_ATR == (1.8, 0.9)
    assert required_midpoint_controls() == (
        ("fade", 1.0, 1.2),
        ("breakout", 1.8, 0.9),
    )
    specs = atr_es_specs()
    fade = [item for item in specs if item.target_atr == 1.0 and item.stop_atr == 1.2]
    breakout = [item for item in specs if item.target_atr == 1.8 and item.stop_atr == 0.9]
    gap = next(item for item in specs if item.config_id == "p2a-gap-es")
    assert len(fade) == 4
    assert len(breakout) == 5
    assert gap.disable_brackets is True
    assert gap.session_filter == "rth"
    assert gap.session_end_flatten is True


@pytest.mark.unit
def test_session_flatten_is_last_rth_bar_not_utc_midnight() -> None:
    rth_last = datetime(2026, 3, 2, 21, 0, tzinfo=UTC)
    bars = (
        _bar(rth_last - timedelta(minutes=10), open_=5000.0, high=5000.25, low=4999.75, close=5000.0),
        _bar(rth_last, open_=5000.0, high=5000.5, low=4999.5, close=5001.0),
        _bar(rth_last + timedelta(minutes=5), open_=5001.0, high=5001.25, low=5000.75, close=5001.0),
        _bar(datetime(2026, 3, 3, 0, 0, tzinfo=UTC), open_=5002.0, high=5002.5, low=5001.5, close=5003.0),
    )
    labels = annotate(bars)
    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    executed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0, 0.0),
        geometry=geometry,
        breaks=(False, False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=2000,
        session_end_flatten=True,
        disable_brackets=True,
    )
    assert executed.trades
    closed = executed.trades[0]
    assert closed.reason == "session_end"
    assert closed.exit_price == pytest.approx(5001.0)
    midnight = bars[-1]
    assert datetime.fromtimestamp(midnight.ts_ns / 1_000_000_000, tz=UTC).hour == 0
    assert closed.exit_price != pytest.approx(midnight.close)


@pytest.mark.unit
def test_unbracket_horizons_are_16_60_120() -> None:
    assert UNBRACKET_HORIZONS == (16, 60, 120)
    geometry = require_geometry(root="ES", target_ticks=16, stop_ticks=8)
    win = ClosedTrade(side=1.0, entry_price=1.0, exit_price=2.0, pnl_ticks=1.0, reason="time_stop")
    loss = ClosedTrade(side=1.0, entry_price=1.0, exit_price=0.0, pnl_ticks=-1.0, reason="time_stop")
    costed = apply_costs(
        gross_returns=(0.01,),
        positions=(1.0,),
        equity=100_000.0,
        spec="ES",
        markets=(MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0),),
    )
    diag = from_trades(
        trades=(win,),
        geometry=geometry,
        costed=costed,
        is_sharpes=(),
        oos_sharpes=(),
        regimes=RegimeSnapshot.missing(),
        n_trials=1,
        n_days=1,
        pct_positive_oos=1.0,
        unbracket_by_horizon={16: (win,), 60: (win, loss), 120: (loss,)},
        target_atr=1.0,
        stop_atr=1.2,
    )
    assert diag.hitrate_unbracket_16 == pytest.approx(1.0)
    assert diag.hitrate_unbracket_60 == pytest.approx(0.5)
    assert diag.hitrate_unbracket_n == pytest.approx(0.5)
    assert diag.hitrate_unbracket_120 == pytest.approx(0.0)


@pytest.mark.unit
def test_dsr_only_kills_stay_killed_and_floor_unchanged() -> None:
    assert FLOOR_DSR_PROBABILITY_MIN == 0.95
    ids = {item.config_id for item in atr_es_specs()}
    assert DSR_ONLY_KILLS <= ids
    assert FLOOR_DSR_PROBABILITY_MIN >= 0.95


@pytest.mark.unit
def test_break_even_is_per_family_geometry_not_one_tick_placeholder() -> None:
    fade = family_break_even_win_rate(target_atr=1.0, stop_atr=1.2)
    breakout = family_break_even_win_rate(target_atr=1.8, stop_atr=0.9)
    gap = family_break_even_win_rate(disable_brackets=True)
    tick = require_geometry(root="ES", target_ticks=16, stop_ticks=8)
    assert fade == pytest.approx(1.2 / 2.2)
    assert breakout == pytest.approx(0.9 / 2.7)
    assert gap != gap
    assert 0.0 < family_break_even_win_rate(tick_geometry=tick) < 1.0
    assert tick.break_even_win_rate != pytest.approx(1.634, abs=0.01)


@pytest.mark.unit
def test_nq_templates_remain_closed() -> None:
    with pytest.raises(NQTemplatesClosed, match="pre-register"):
        assert_nq_templates_closed(("ES", "NQ"))
    assert_nq_templates_closed(("ES", "MES"))
    assert all(item.instrument != "NQ" for item in atr_es_specs())
