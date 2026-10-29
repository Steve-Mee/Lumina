"""Drift-aware multi-seed null (onderzoeksteam 2026-10-29 16:03)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.cycles.daily import daily_market_returns, daily_net_tape, unique_sessions
from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.null_model import (
    NULL_A2_MAX_SHARE,
    NULL_N_SEEDS,
    NULL_SEED_BASE,
    classify_null_a2,
    default_block_seeds,
    default_null_seeds,
    drift_aware_null_signals,
    fail_closed_a2_cap,
    majority_a2_cap,
    max_a2_hits,
    partition_session_windows,
    remap_session_net,
    session_open_close,
    signal_map_by_session,
    week_block_shuffle_signals,
)
from lumina_research.cycles.positive_control import (
    build_null_signals,
    execute_control,
    run_controls,
    rth_session_direction,
    shuffle_signals,
)
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.proof.cli import build_parser, main as proof_main
from lumina_research.validation.cost_model import apply_costs
from lumina_research.validation.trial_registry import TrialRegistry
from tests.research.test_phase5_p2_fixes import _bar, _control_tape

UTC = timezone.utc


def _all_up_tape() -> tuple:
    rows: list[ResearchBar] = []
    day = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    session_index = 0
    while session_index < 22:
        if day.weekday() < 5:
            price = 5000.0
            step = 2.0 + 0.25 * float(session_index % 5)
            for index in range(24):
                ts = day + timedelta(minutes=index)
                nxt = price + step
                rows.append(
                    _bar(
                        ts,
                        open_=price,
                        high=nxt + 0.25,
                        low=price - 0.25,
                        close=nxt,
                        volume=8_000.0,
                    )
                )
                price = nxt
            session_index += 1
        day += timedelta(days=1)
    prepared = prepare_tape("MES", tuple(rows))
    return prepared, rth_session_direction(prepared.bars, prepared.session_dates, prepared.rth)


@pytest.mark.unit
def test_locked_seed_table() -> None:
    seeds = default_null_seeds()
    assert NULL_N_SEEDS == 32
    assert len(seeds) == 32
    assert seeds[0] == NULL_SEED_BASE == 20261029
    assert seeds[-1] == 20261060
    assert len(set(seeds)) == 32
    assert max_a2_hits(32) == 3
    assert fail_closed_a2_cap(32) == 3
    assert majority_a2_cap(32) == 16
    assert NULL_A2_MAX_SHARE == 0.10
    assert classify_null_a2(3, 32).status == "reliable"
    assert classify_null_a2(4, 32).status == "borderline"
    assert classify_null_a2(4, 32).reliable is True
    assert classify_null_a2(5, 32).status == "unreliable"
    assert classify_null_a2(5, 32).exact == "5/32"
    assert len(default_block_seeds()) == 8
    assert default_block_seeds()[0] == 20261129


@pytest.mark.unit
def test_partition_covers_all_sessions() -> None:
    windows = partition_session_windows(22, is_size=6, oos_size=2, embargo=1)
    covered = [index for start, end in windows for index in range(start, end)]
    assert covered == list(range(22))
    assert windows[0] == (0, 6)
    assert windows[1] == (6, 7)


@pytest.mark.unit
def test_all_up_shuffle_is_identity_but_drift_aware_balances() -> None:
    prepared, planted = _all_up_tape()
    assert all(value >= 0.0 for value in planted)
    assert sum(1 for value in planted if value > 0.0) == 22
    shuffled = shuffle_signals(planted, seed=20261029)
    assert shuffled == planted
    oc = session_open_close(prepared.bars, prepared.session_dates, prepared.rth)
    null = drift_aware_null_signals(
        planted,
        seed=20261029,
        session_dates=prepared.session_dates,
        oc_by_date=oc,
        is_size=6,
        oos_size=2,
    )
    sessions = unique_sessions(prepared.session_dates)
    sign_map = signal_map_by_session(null, prepared.session_dates)
    for start, end in partition_session_windows(len(sessions), is_size=6, oos_size=2):
        block = [sign_map[day] for day in sessions[start:end] if day in sign_map]
        n_pos = sum(1 for value in block if value > 0.0)
        n_neg = sum(1 for value in block if value < 0.0)
        assert abs(n_pos - n_neg) <= 1
    assert null != planted


@pytest.mark.unit
def test_week_block_preserves_sign_multiset() -> None:
    prepared, planted = _all_up_tape()
    blocked = week_block_shuffle_signals(planted, prepared.session_dates, seed=20261129)
    assert sorted(blocked) == sorted(planted)


@pytest.mark.unit
def test_remap_matches_execute_control_on_short_tape() -> None:
    prepared = _control_tape()
    planted = rth_session_direction(prepared.bars, prepared.session_dates, prepared.rth)
    oc = session_open_close(prepared.bars, prepared.session_dates, prepared.rth)
    null = build_null_signals(
        planted,
        seed=20261029,
        session_dates=prepared.session_dates,
        oc_by_date=oc,
        is_size=6,
        oos_size=2,
    )
    pos_exec = execute_control(prepared, planted, root="MES")
    null_exec = execute_control(prepared, null, root="MES")
    pos_costed = apply_costs(
        gross_returns=pos_exec.gross,
        positions=pos_exec.positions,
        equity=100_000.0,
        spec="MES",
        markets=pos_exec.markets,
    )
    null_costed = apply_costs(
        gross_returns=null_exec.gross,
        positions=null_exec.positions,
        equity=100_000.0,
        spec="MES",
        markets=null_exec.markets,
    )
    sessions = unique_sessions(prepared.session_dates)
    daily_gross = daily_net_tape(pos_exec.gross, prepared.session_dates)[0]
    daily_net = daily_net_tape(pos_costed.net_returns, prepared.session_dates)[0]
    remapped = remap_session_net(
        daily_gross=daily_gross,
        daily_net=daily_net,
        sessions=sessions,
        planted_signs=signal_map_by_session(planted, prepared.session_dates),
        null_signs=signal_map_by_session(null, prepared.session_dates),
    )
    executed_daily = daily_net_tape(null_costed.net_returns, prepared.session_dates)[0]
    assert remapped == pytest.approx(executed_daily, abs=1e-12)


@pytest.mark.unit
def test_run_controls_multiseed_accepts_balanced_tape(tmp_path: Path) -> None:
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
    assert report.null_audit is not None
    assert report.null_audit.n_seeds == 32
    assert report.null_audit.reliable is True
    assert report.null_audit.exact_a2 == f"{report.null_audit.n_a2}/32"
    assert report.null_audit.exact_edge == f"{report.null_audit.n_edge}/32"
    assert report.null_audit.n_edge <= 3 or report.null_audit.status == "borderline"
    assert report.null_audit.max_a2 == 3
    assert report.null_audit.ten_pct_cap == 3
    assert report.null_audit.n_trials_this_root == 1 + 32 + 8
    assert all(seed.kind == "block" for seed in report.null_audit.block_seeds)
    assert len(report.null_audit.block_seeds) == 8


@pytest.mark.unit
def test_cli_null_audit_cycle_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "null-audit"])
    assert args.cycle == "null-audit"


@pytest.mark.unit
def test_cli_null_audit_fail_closed_without_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cycle:
        method_ready = False

    monkeypatch.setattr("lumina_research.proof.cli.run_null_audit", lambda **_kwargs: _Cycle())
    assert proof_main(["research", "--cycle", "null-audit", "--work-dir", str(tmp_path)]) == 2
