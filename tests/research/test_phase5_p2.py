"""P2 first research cycle: holdout pin, gaps, rolls, independence, daily WF sizes."""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_research.cycles.catalog import catalog
from lumina_research.cycles.daily import daily_net_tape, unique_sessions
from lumina_research.cycles.data import DataStatus, LoadedTape, ResearchBar, discover_data
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.gaps import in_known_gap, interval_crosses_gap
from lumina_research.cycles.geometry import floors_for, require_geometry
from lumina_research.cycles.holdout import (
    P2_HOLDOUT_START_NS,
    P2_HOLDOUT_START_UTC,
    P2_PIN_MIN_BARS,
    HoldoutLocked,
    access_bars,
    holdout_start_ns,
)
from lumina_research.cycles.independence import IndependenceRow, pearson_corr, select_independent
from lumina_research.cycles.manifest import write_data_manifest
from lumina_research.cycles import p2_cycle as p2_cycle_mod
from lumina_research.cycles.p2_cycle import (
    HoldoutEvalRow,
    clear_materialize_cache,
    evaluate_holdout,
    materialize_spec,
    pin_tape,
    prepare_for_purpose,
    window_note,
    with_walk_forward_sizes,
)
from lumina_research.cycles.prepare import prepare_tape
from lumina_research.cycles.report import CycleReport, CycleRow, write_cycle_reports
from lumina_research.cycles.rolls import NT8_ROLL_SET, is_roll_session
from lumina_research.cycles import runner as runner_mod
from lumina_research.cycles.runner import (
    _holdout_rows,
    _independence,
    _is_real_p2,
    _usable_for_gate,
    run_research_cycles,
)
from lumina_research.cycles.seal import CSV_SHA256, ZIP_SHA256, load_seal, seal_holdout
from lumina_research.cycles.sessions import annotate, utc_from_ns
from lumina_research.cycles.strategies import simulate
from lumina_research.cycles.wf_sizes import TARGET_OOS_WINDOWS, walk_forward_sizes
from lumina_research.validation.walk_forward import WalkForwardError

UTC = timezone.utc


def _bar(ts: datetime, close: float, volume: float = 1_000.0) -> ResearchBar:
    ns = int(ts.timestamp() * 1_000_000_000)
    return ResearchBar(ts_ns=ns, open=close, high=close + 0.5, low=close - 0.5, close=close, volume=volume)


def _minutes(start: datetime, n: int, px: float = 5_000.0, step_px: float = 0.0) -> tuple[ResearchBar, ...]:
    rows: list[ResearchBar] = []
    price = px
    for index in range(n):
        rows.append(_bar(start + timedelta(minutes=index), price))
        price += step_px
    return tuple(rows)


def _span_bars(n: int = 400, px: float = 5_000.0) -> tuple[ResearchBar, ...]:
    start = datetime(2023, 10, 28, tzinfo=UTC)
    end = datetime(2026, 10, 28, tzinfo=UTC)
    step = (end - start).total_seconds() / float(max(n - 1, 1))
    rows: list[ResearchBar] = []
    price = px
    for index in range(n):
        ts = datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC)
        rows.append(_bar(ts, price))
        price += 0.01
    return tuple(rows)


def _write_csv(path: Path, bars: tuple[ResearchBar, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,open,high,low,close,volume"]
    for bar in bars:
        stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=UTC).isoformat()
        lines.append(f"{stamp},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.unit
def test_known_gaps_are_dropped_never_filled() -> None:
    before = _bar(datetime(2026, 6, 9, 14, 59, tzinfo=UTC), 5000.0)
    inside = _bar(datetime(2026, 6, 9, 15, 10, tzinfo=UTC), 5010.0)
    after = _bar(datetime(2026, 6, 9, 15, 40, tzinfo=UTC), 5020.0)
    assert in_known_gap("MES", inside.ts_ns) is True
    assert in_known_gap("MES", before.ts_ns) is False
    extra = _minutes(datetime(2026, 6, 9, 10, 0, tzinfo=UTC), 241)
    prepared = prepare_tape("MES", extra + (before, inside, after))
    kept_ts = {item.ts_ns for item in prepared.bars}
    assert inside.ts_ns not in kept_ts
    assert before.ts_ns in kept_ts
    assert after.ts_ns in kept_ts
    assert prepared.dropped >= 1
    mids = {0.5 * (before.close + after.close)}
    assert after.close not in mids or after.close == 5020.0
    assert interval_crosses_gap("MES", before.ts_ns, after.ts_ns) is True
    after_index = next(i for i, item in enumerate(prepared.bars) if item.ts_ns == after.ts_ns)
    assert prepared.breaks[after_index] is True


@pytest.mark.unit
def test_roll_boundary_zeros_return_and_flattens() -> None:
    assert date(2024, 3, 11) in NT8_ROLL_SET
    assert is_roll_session(date(2024, 3, 11)) is True
    pre = datetime(2024, 3, 10, 18, 0, tzinfo=UTC)
    bars = _minutes(pre, 240, px=5000.0)
    roll = _bar(datetime(2024, 3, 10, 22, 1, tzinfo=UTC), 5300.0)
    tape = prepare_tape("MES", bars + (roll,))
    labels = annotate(tape.bars)
    roll_index = next(i for i, item in enumerate(tape.bars) if item.ts_ns == roll.ts_ns)
    assert labels.session_dates[roll_index] == date(2024, 3, 11)
    assert tape.breaks[roll_index] is True
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    gross, positions, _markets = simulate(
        family="mean_reversion",
        bars=tape.bars,
        geometry=geo,
        lookback=10,
        threshold=1.5,
        mode="fade",
        breaks=tape.breaks,
        session_dates=tape.session_dates,
        rth=tape.rth,
        quiet=tape.quiet,
    )
    assert gross[roll_index] == 0.0
    assert positions[roll_index] == 0.0


@pytest.mark.unit
def test_p2_holdout_is_pinned_before_selection() -> None:
    start = datetime(2026, 1, 25, tzinfo=UTC)
    bars = _minutes(start, P2_PIN_MIN_BARS)
    tape = LoadedTape(instrument="MES", bar_size="1m", path=Path("mes.csv"), bars=bars)
    pinned = pin_tape(tape)
    assert pinned.holdout_start_ns == P2_HOLDOUT_START_NS
    train = access_bars(pinned, purpose="gate")
    locked = access_bars(pinned, purpose="evaluation")
    assert train[-1].ts_ns < P2_HOLDOUT_START_NS <= locked[0].ts_ns
    assert holdout_start_ns(bars, pinned_start_ns=P2_HOLDOUT_START_NS) == P2_HOLDOUT_START_NS
    small = pin_tape(LoadedTape(instrument="MES", bar_size="1m", path=Path("x.csv"), bars=bars[:400]))
    assert small.holdout_start_ns is None
    assert P2_HOLDOUT_START_UTC.isoformat().startswith("2026-01-28T23:00:00")


@pytest.mark.unit
def test_seal_refuses_sha_mismatch_and_roundtrips(tmp_path: Path) -> None:
    bars = _span_bars()
    path = tmp_path / "MES" / "1m" / "mes.csv"
    _write_csv(path, bars)
    tape = LoadedTape(instrument="MES", bar_size="1m", path=path, bars=bars, holdout_start_ns=P2_HOLDOUT_START_NS)
    with pytest.raises(HoldoutLocked, match="sha256 mismatch"):
        seal_holdout((tape,), report_dir=tmp_path / "rep", require_known_files=True)
    body = seal_holdout((tape,), report_dir=tmp_path / "rep", require_known_files=False)
    assert body["holdout_start_ns"] == P2_HOLDOUT_START_NS
    assert "seal_sha256" in body
    loaded = load_seal(tmp_path / "rep")
    assert loaded["holdout_start_ns"] == P2_HOLDOUT_START_NS
    with pytest.raises(HoldoutLocked, match="missing"):
        load_seal(tmp_path / "empty")
    bad = tmp_path / "rep" / "phase5_p2_holdout_seal.json"
    payload = json.loads(bad.read_text(encoding="utf-8"))
    payload["holdout_start_ns"] = 1
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(HoldoutLocked, match="drifted"):
        load_seal(tmp_path / "rep")
    bogus = tmp_path / "nope"
    bogus.mkdir()
    (bogus / "phase5_p2_holdout_seal.json").write_text("[]\n", encoding="utf-8")
    with pytest.raises(HoldoutLocked, match="not an object"):
        load_seal(bogus)


@pytest.mark.unit
def test_independence_family_and_corr_fail_closed() -> None:
    a = tuple(float(index) for index in range(20))
    b = tuple(float(index) for index in range(20))
    c = tuple(float((-1) ** index) for index in range(20))
    rows = select_independent(
        config_ids=("a", "b", "c"),
        families=("mean_reversion", "mean_reversion", "overnight_gap"),
        series=(a, b, c),
        scores=(1.0, 0.5, 0.9),
    )
    by_id = {item.config_id: item for item in rows}
    assert by_id["a"].kept is True
    assert by_id["b"].kept is False
    assert by_id["b"].reason == "duplicate_family"
    assert by_id["c"].kept is True
    assert pearson_corr(a, b) == pytest.approx(1.0)
    assert math.isnan(pearson_corr((1.0, 1.0), (2.0, 2.0)))
    correlated = select_independent(
        config_ids=("x", "y"),
        families=("vwap_distance", "close_reversal"),
        series=(a, b),
        scores=(1.0, 1.0),
    )
    assert correlated[0].kept is True
    assert correlated[1].kept is False
    assert "corr_" in correlated[1].reason
    with pytest.raises(ValueError, match="align"):
        select_independent(config_ids=("x",), families=("a", "b"), series=(a,), scores=(1.0,))


@pytest.mark.unit
def test_walk_forward_sizes_are_six_to_eight() -> None:
    is_size, oos_size, formed = walk_forward_sizes(600)
    assert 6 <= formed <= TARGET_OOS_WINDOWS
    assert is_size >= 2 and oos_size >= 2
    with pytest.raises(WalkForwardError):
        walk_forward_sizes(8)
    with pytest.raises(WalkForwardError):
        walk_forward_sizes(100, embargo=-1)


@pytest.mark.unit
def test_daily_resample_and_session_labels() -> None:
    start = datetime(2026, 3, 2, 14, 31, tzinfo=UTC)
    bars = _minutes(start, 5, px=5000.0)
    labels = annotate(bars)
    assert len(unique_sessions(labels.session_dates)) >= 1
    assert labels.rth[0] is True
    net = (0.1, -0.05, 0.02, 0.0, 0.03)
    daily, positions, markets = daily_net_tape(net, labels.session_dates)
    assert len(daily) == len(unique_sessions(labels.session_dates))
    assert all(item == 0.0 for item in positions)
    assert len(markets) == len(daily)
    with pytest.raises(ValueError, match="align"):
        daily_net_tape((0.1,), labels.session_dates)
    with pytest.raises(ValueError, match="empty"):
        daily_net_tape((), ())
    assert utc_from_ns(bars[0].ts_ns).tzinfo is not None


@pytest.mark.unit
def test_materialize_cache_and_holdout_eval() -> None:
    clear_materialize_cache()
    bars = _minutes(datetime(2025, 1, 6, 15, 0, tzinfo=UTC), 300)
    prepared = prepare_tape("MES", bars)
    spec = first_cycle_specs()[0]
    first = materialize_spec(spec, prepared)
    second = materialize_spec(spec, prepared)
    assert first[0] is second[0]
    row = evaluate_holdout(spec, prepared)
    assert row.config_id == spec.config_id
    assert row.n_days == len(first[0])
    assert window_note(()) == "n/a"
    assert "walk-forward" in window_note((spec,))
    sized = with_walk_forward_sizes((spec,), {"MES": prepared})
    assert sized[0].is_size >= 2


@pytest.mark.unit
def test_tick_floors_and_zip_hashes_are_frozen() -> None:
    assert floors_for("MES") == (16, 8)
    assert floors_for("MNQ") == (16, 8)
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    assert geo.break_even_win_rate > 0.0
    assert ZIP_SHA256["MES"].startswith("c5c094a1")
    assert ZIP_SHA256["MNQ"].startswith("a1cefabd")
    assert len(CSV_SHA256["MES"]) == 64
    specs = first_cycle_specs()
    assert len(specs) == 12
    assert {item.instrument for item in specs} <= {"MES", "MNQ"}
    assert all(item.target_ticks >= 16 and item.stop_ticks >= 8 for item in specs)


@pytest.mark.unit
def test_manifest_and_fixture_cycle_do_not_claim_real_p2(tmp_path: Path) -> None:
    bars = _span_bars()
    mes = tmp_path / "data" / "research" / "MES" / "1m" / "mes.csv"
    mnq = tmp_path / "data" / "research" / "MNQ" / "1m" / "mnq.csv"
    _write_csv(mes, bars)
    _write_csv(mnq, bars)
    tape = LoadedTape(instrument="MES", bar_size="1m", path=mes, bars=bars)
    write_data_manifest((tape,), repo_root=tmp_path, dropped={"MES": 0})
    body = json.loads((tmp_path / "data" / "research" / "manifest.json").read_text(encoding="utf-8"))
    assert body["conventions"]["gaps"] == "exclude, never fill"
    status = discover_data(repo_root=tmp_path)
    assert _is_real_p2(status) is False
    assert _usable_for_gate(status) is True
    spec = catalog()[0]
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
        specs=(spec,),
    )
    assert result.report.n_tested == 1
    assert result.report.holdout_seal_sha256 == ""
    assert (tmp_path / "reports" / "phase5_p2_results.md").is_file()
    train = prepare_for_purpose(tape, purpose="gate")
    assert len(train.bars) >= 241


@pytest.mark.unit
def test_mnq_missing_days_are_excluded() -> None:
    inside = _bar(datetime(2025, 6, 30, 12, 0, tzinfo=UTC), 18000.0)
    assert in_known_gap("MNQ", inside.ts_ns) is True
    assert in_known_gap("MES", inside.ts_ns) is False
    cme = _bar(datetime(2025, 11, 28, 10, 0, tzinfo=UTC), 5000.0)
    assert in_known_gap("MES", cme.ts_ns) is True
    assert in_known_gap("MNQ", cme.ts_ns) is True
    undefined = select_independent(
        config_ids=("p", "q"),
        families=("vwap_distance", "close_reversal"),
        series=((1.0, 1.0, 1.0), (1.0, 2.0, 3.0)),
        scores=(1.0, 0.5),
    )
    assert undefined[0].kept is True
    assert undefined[1].kept is False
    assert undefined[1].reason == "corr_undefined"
    assert interval_crosses_gap("MES", 10, 10) is False


@pytest.mark.unit
def test_daily_resample_materialize_and_report_sections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(p2_cycle_mod, "DAILY_RESAMPLE_MIN_BARS", 50)
    clear_materialize_cache()
    bars = _minutes(datetime(2025, 1, 6, 15, 0, tzinfo=UTC), 300)
    prepared = prepare_tape("MES", bars)
    spec = first_cycle_specs()[0]
    tape = materialize_spec(spec, prepared)
    assert len(tape[0]) == len(unique_sessions(prepared.session_dates))
    assert all(pos == 0.0 for pos in tape[1])
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    row = CycleRow(
        hypothesis_id="h",
        config_id=spec.config_id,
        template_id=spec.template_id,
        family=spec.family,
        instrument="MES",
        pre_registered=True,
        tested=True,
        passed=True,
        reject_reasons=(),
        pbo=0.1,
        dsr=0.99,
        wfe=0.8,
        n_oos_windows=8,
        median_oos=0.01,
        geometry=geo,
        death_reason="survived",
    )
    report = CycleReport(
        n_hypotheses=1,
        n_tested=1,
        n_killed=0,
        n_survivors=1,
        kill_rate=0.0,
        kill_rate_flag="within_expectation",
        cost_bands=(),
        data=DataStatus(usable=True, tapes=(), searched=(), missing=(), required={}),
        rows=(row,),
        geometry_by_root=(geo,),
        stopped=False,
        stop_reason="",
        holdout_seal_sha256="abc",
        wf_note="walk-forward",
        independence=(
            IndependenceRow(
                config_id=spec.config_id, family=spec.family, kept=True, reason="independent", max_abs_corr=0.1
            ),
        ),
        holdout_eval=(
            HoldoutEvalRow(
                config_id=spec.config_id,
                family=spec.family,
                instrument="MES",
                n_days=10,
                mean_net=0.001,
                sharpe=0.5,
                n_positive_days=6,
                max_drawdown=0.02,
            ),
        ),
    )
    _json_path, md_path = write_cycle_reports(report, tmp_path / "rep")
    text = md_path.read_text(encoding="utf-8")
    assert "Holdout seal" in text
    assert "Independent survivors" in (tmp_path / "rep" / "phase5_p2_results.md").read_text(encoding="utf-8")
    fake = SimpleNamespace(
        passed=True,
        config_id=spec.config_id,
        pbo=SimpleNamespace(pbo=0.1),
        dsr=SimpleNamespace(probability=0.99),
    )
    indep = _independence((spec,), (fake,), {"MES": prepared})  # type: ignore[arg-type]
    assert indep[0].kept is True
    rows = _holdout_rows((spec,), (fake,), {"MES": prepared}, independence=indep)  # type: ignore[arg-type]
    assert rows[0].config_id == spec.config_id
    dropped = (
        IndependenceRow(
            config_id=spec.config_id, family=spec.family, kept=False, reason="duplicate_family", max_abs_corr=None
        ),
    )
    assert _holdout_rows((spec,), (fake,), {"MES": prepared}, independence=dropped) == ()  # type: ignore[arg-type]


@pytest.mark.unit
def test_cycle_report_rewrites_data_dir_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "research-root"
    csv = data_root / "MES" / "1m" / "mes.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text("x\n", encoding="utf-8")
    monkeypatch.setenv("LUMINA_RESEARCH_DATA_DIR", str(data_root))
    geo = require_geometry(root="MES", target_ticks=16, stop_ticks=8)
    tape = LoadedTape(
        instrument="MES",
        bar_size="1m",
        path=csv,
        bars=_minutes(datetime(2025, 1, 6, 15, 0, tzinfo=UTC), 3),
    )
    report = CycleReport(
        n_hypotheses=0,
        n_tested=0,
        n_killed=0,
        n_survivors=0,
        kill_rate=1.0,
        kill_rate_flag="expected_high_kill",
        cost_bands=(),
        data=DataStatus(
            usable=True,
            tapes=(tape,),
            searched=(str(data_root), str(tmp_path / "other")),
            missing=("ES",),
            required={},
        ),
        rows=(),
        geometry_by_root=(geo,),
        stopped=False,
        stop_reason="",
    )
    write_cycle_reports(report, tmp_path / "rep")
    json_text = (tmp_path / "rep" / "phase5_research_cycles.json").read_text(encoding="utf-8")
    md_text = (tmp_path / "rep" / "phase5_research_cycles.md").read_text(encoding="utf-8")
    assert "$LUMINA_RESEARCH_DATA_DIR/MES/1m/mes.csv" in json_text
    assert str(data_root) not in json_text
    assert "$LUMINA_RESEARCH_DATA_DIR" in md_text
    assert str(tmp_path / "other") in json_text


@pytest.mark.unit
def test_real_p2_branch_seals_before_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []
    bars = _span_bars(n=1200)
    _write_csv(tmp_path / "data" / "research" / "MES" / "1m" / "mes.csv", bars)
    _write_csv(tmp_path / "data" / "research" / "MNQ" / "1m" / "mnq.csv", bars)

    def _real(_status: object) -> bool:
        order.append("real")
        return True

    def _seal(
        tapes: object,
        *,
        report_dir: Path,
        require_known_files: bool = True,
        **_kwargs: object,
    ) -> dict[str, object]:
        del tapes, require_known_files, _kwargs
        order.append("seal")
        mes = LoadedTape(
            instrument="MES",
            bar_size="1m",
            path=tmp_path / "data" / "research" / "MES" / "1m" / "mes.csv",
            bars=bars,
        )
        return seal_holdout((mes,), report_dir=report_dir, require_known_files=False)

    monkeypatch.setattr(runner_mod, "_is_real_p2", _real)
    monkeypatch.setattr(runner_mod, "seal_holdout", _seal)
    spec = first_cycle_specs()[0]
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
        specs=(spec,),
    )
    assert order[0] == "real"
    assert "seal" in order
    assert result.report.holdout_seal_sha256
    assert result.report.n_tested == 1
