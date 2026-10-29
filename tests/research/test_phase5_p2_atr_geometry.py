"""ATR/points geometry, ES-only July gaps, extra diagnostics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.cycles.atr import causal_session_atr, points_to_ticks
from lumina_research.cycles.atr_cycle import ATR_SEAL_NAME, atr_es_specs
from lumina_research.cycles.data import LoadedTape
from lumina_research.cycles.diagnostics import from_trades
from lumina_research.cycles.execution import ClosedTrade, ExecutionRefused, run_execution
from lumina_research.cycles.gaps import in_known_gap
from lumina_research.cycles.geometry import require_geometry
from lumina_research.cycles.holdout import HoldoutLocked
from lumina_research.cycles.positive_control import horizon_note
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.cycles.seal import ES_NQ_SEAL_NAME, ES_NQ_SEAL_SHA256, seal_holdout
from lumina_research.cycles.sessions import annotate
from lumina_research.proof.cli import build_parser
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import MarketSnapshot, apply_costs
from lumina_research.validation.types import RegimeSnapshot
from tests.research.test_phase5_p2 import _span_bars
from tests.research.test_phase5_p2_fixes import _bar

UTC = timezone.utc


@pytest.mark.unit
def test_atr_es_grid_is_ten_es_configs() -> None:
    specs = atr_es_specs()
    assert len(specs) == 10
    assert {item.instrument for item in specs} == {"ES"}
    assert all(item.time_stop_bars == 2000 for item in specs)
    assert all(item.session_end_flatten for item in specs)
    gap = next(item for item in specs if item.config_id == "p2a-gap-es")
    assert gap.disable_brackets is True
    assert gap.target_atr is None
    fade = next(item for item in specs if item.config_id == "p2a-mr-es")
    assert fade.target_atr == 1.0 and fade.stop_atr == 1.2
    bo = next(item for item in specs if item.config_id == "p2a-or-bo-es")
    assert bo.target_atr == 1.8 and bo.stop_atr == 0.9
    templates = {item.template_id for item in specs}
    assert "close_reversal" not in templates
    assert "volume_imbalance" not in templates
    assert all(item.session_filter == "rth" for item in specs)
    assert ATR_SEAL_NAME == "phase5_p2_atr_es_holdout_seal.json"
    assert ATR_SEAL_NAME != "phase5_p2_es_nq_holdout_seal.json"


@pytest.mark.unit
def test_july_train_gap_is_es_and_mnq_not_nq_or_mes() -> None:
    ts = int(datetime(2025, 7, 14, 18, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    assert in_known_gap("ES", ts) is True
    assert in_known_gap("MNQ", ts) is True
    assert in_known_gap("NQ", ts) is False
    assert in_known_gap("MES", ts) is False
    thin = int(datetime(2025, 11, 28, 18, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    assert in_known_gap("ES", thin) is True
    assert in_known_gap("NQ", thin) is True
    hold = int(datetime(2026, 4, 23, 18, 0, tzinfo=UTC).timestamp() * 1_000_000_000)
    assert in_known_gap("ES", hold) is True
    assert in_known_gap("NQ", hold) is False


@pytest.mark.unit
def test_causal_session_atr_ignores_future_sessions() -> None:
    rows = []
    day = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    session_index = 0
    while session_index < 6:
        if day.weekday() < 5:
            price = 100.0 + 10.0 * float(session_index)
            for index in range(8):
                ts = day + timedelta(minutes=index)
                rows.append(
                    _bar(
                        ts,
                        open_=price,
                        high=price + 1.0 + float(session_index),
                        low=price - 0.25,
                        close=price + 0.5,
                        volume=5_000.0,
                    )
                )
            session_index += 1
        day += timedelta(days=1)
    prepared = prepare_tape("ES", tuple(rows))
    atr = causal_session_atr(prepared.bars, prepared.session_dates, prepared.rth, n_sessions=14)
    first_session = prepared.session_dates[0]
    first_vals = {atr[i] for i, session in enumerate(prepared.session_dates) if session == first_session}
    assert first_vals == {0.0}
    later = [atr[i] for i, session in enumerate(prepared.session_dates) if session != first_session]
    assert any(value > 0.0 for value in later)


@pytest.mark.unit
def test_from_trades_counts_exit_reasons_and_points() -> None:
    geometry = require_geometry(root="ES", target_ticks=16, stop_ticks=8)
    trades = (
        ClosedTrade(
            side=1.0,
            entry_price=5000.0,
            exit_price=5004.0,
            pnl_ticks=16.0,
            reason="target",
            mfe_ticks=20.0,
            mae_ticks=2.0,
        ),
        ClosedTrade(
            side=1.0, entry_price=5000.0, exit_price=4998.0, pnl_ticks=-8.0, reason="stop", mfe_ticks=1.0, mae_ticks=8.0
        ),
        ClosedTrade(
            side=1.0,
            entry_price=5000.0,
            exit_price=5001.0,
            pnl_ticks=4.0,
            reason="session_end",
            mfe_ticks=5.0,
            mae_ticks=1.0,
        ),
    )
    gross = (0.01, -0.002, 0.004)
    positions = (1.0, 1.0, 0.0)
    markets = tuple(MarketSnapshot(volume=5_000.0, average_volume=8_000.0, volatility_price=1.0) for _ in gross)
    costed = apply_costs(gross_returns=gross, positions=positions, equity=100_000.0, spec="ES", markets=markets)
    diag = from_trades(
        trades=trades,
        geometry=geometry,
        costed=costed,
        is_sharpes=(),
        oos_sharpes=(),
        regimes=RegimeSnapshot.missing(),
        n_trials=1,
        n_days=3,
        pct_positive_oos=0.0,
        unbracket_trades=trades[:1],
        one_r_trades=trades[:2],
    )
    assert diag.exit_target == 1
    assert diag.exit_stop == 1
    assert diag.exit_session_end == 1
    assert diag.gross_ticks == pytest.approx(12.0)
    assert diag.gross_points == pytest.approx(3.0)
    assert diag.hitrate_unbracket_n == pytest.approx(1.0)
    assert diag.hitrate_1r1r == pytest.approx(0.5)


@pytest.mark.unit
def test_cli_atr_es_flag() -> None:
    args = build_parser().parse_args(["research", "--cycle", "atr-es"])
    assert args.cycle == "atr-es"


@pytest.mark.unit
def test_disable_brackets_exits_on_session_end() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    bars = tuple(
        _bar(
            start + timedelta(minutes=index),
            open_=entry + 0.05 * index,
            high=entry + 0.5 + 0.05 * index,
            low=entry - 0.5 + 0.05 * index,
            close=entry + 0.05 * index,
            volume=8_000.0,
        )
        for index in range(12)
    )
    labels = annotate(bars)
    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    executed = run_execution(
        bars=bars,
        signals=(1.0,) + tuple(0.0 for _ in range(len(bars) - 1)),
        geometry=geometry,
        breaks=tuple(False for _ in bars),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=2000,
        session_end_flatten=True,
        disable_brackets=True,
    )
    assert executed.trades
    assert all(item.reason == "session_end" for item in executed.trades)


@pytest.mark.unit
def test_points_to_ticks_equal_for_es_and_mes() -> None:
    es = spec_for("ES").tick_size
    mes = spec_for("MES").tick_size
    assert es == mes == 0.25
    assert points_to_ticks(1.0, tick_size=es) == points_to_ticks(1.0, tick_size=mes) == 4


@pytest.mark.unit
def test_atr_bracket_exits_at_atr_points_not_tick_floors() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    entry = 5000.0
    atr_points = 2.0
    target = entry + atr_points
    bars = (
        _bar(start, open_=entry, high=entry + 0.25, low=entry - 0.25, close=entry),
        _bar(start + timedelta(minutes=1), open_=entry + 0.1, high=entry + 0.2, low=entry - 0.4, close=entry + 0.1),
        _bar(start + timedelta(minutes=2), open_=entry + 0.2, high=target + 0.5, low=entry, close=target + 0.2),
    )
    labels = annotate(bars)
    geometry = require_geometry(root="ES", target_ticks=16, stop_ticks=8)
    executed = run_execution(
        bars=bars,
        signals=(1.0, 0.0, 0.0),
        geometry=geometry,
        breaks=(False, False, False),
        rth=labels.rth,
        session_dates=labels.session_dates,
        session_filter="rth",
        time_stop_bars=2000,
        session_end_flatten=False,
        atr_points=(atr_points, atr_points, atr_points),
        target_atr=1.0,
        stop_atr=1.0,
    )
    assert executed.trades
    closed = executed.trades[0]
    assert closed.reason == "target"
    assert closed.exit_price == pytest.approx(target)
    assert closed.mfe_ticks >= closed.pnl_ticks


@pytest.mark.unit
def test_target_atr_requires_stop_atr() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = tuple(
        _bar(start + timedelta(minutes=index), open_=5000.0, high=5000.25, low=4999.75, close=5000.0)
        for index in range(3)
    )
    labels = annotate(bars)
    geometry = require_geometry(root="ES", target_ticks=1, stop_ticks=1)
    with pytest.raises(ExecutionRefused, match="together"):
        run_execution(
            bars=bars,
            signals=(1.0, 0.0, 0.0),
            geometry=geometry,
            breaks=(False, False, False),
            rth=labels.rth,
            session_dates=labels.session_dates,
            target_atr=1.0,
        )


@pytest.mark.unit
def test_atr_seal_does_not_overwrite_live_es_nq_seal(tmp_path: Path) -> None:
    live = Path("experiments/reports") / ES_NQ_SEAL_NAME
    (tmp_path / ES_NQ_SEAL_NAME).write_text(live.read_text(encoding="utf-8"), encoding="utf-8")
    bars = _span_bars()
    csv = tmp_path / "ES" / "1m" / "es.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    tape = LoadedTape(instrument="ES", bar_size="1m", path=csv, bars=bars)
    with pytest.raises(HoldoutLocked, match="refusing to overwrite live ES/NQ"):
        seal_holdout((tape,), report_dir=tmp_path, require_known_files=False, filename=ES_NQ_SEAL_NAME)
    committed = Path(tmp_path / ES_NQ_SEAL_NAME).read_text(encoding="utf-8")
    assert ES_NQ_SEAL_SHA256 in committed
    alt = seal_holdout(
        (tape,),
        report_dir=tmp_path,
        require_known_files=False,
        filename=ATR_SEAL_NAME,
    )
    assert alt["seal_sha256"] != ES_NQ_SEAL_SHA256
    assert (tmp_path / ATR_SEAL_NAME).is_file()
    still = Path(tmp_path / ES_NQ_SEAL_NAME).read_text(encoding="utf-8")
    assert ES_NQ_SEAL_SHA256 in still


@pytest.mark.unit
def test_atr_control_horizon_note_is_not_unclipped_20000() -> None:
    atr = horizon_note("atr")
    unclipped = horizon_note("unclipped")
    assert "1.5" in atr and "ATR" in atr
    assert "20000/20000" not in atr
    assert "20000/20000" in unclipped
    with pytest.raises(ValueError, match="unknown control geometry_mode"):
        horizon_note("ticks")
