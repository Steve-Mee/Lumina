"""Step 4: same 12 templates, holdout unopened, real CSVs not in git."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.first_cycle import first_cycle_specs
from lumina_research.cycles.p2_cycle import clear_materialize_cache
from lumina_research.cycles.runner import run_research_cycles

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


def _write_csv(path: Path, bars: tuple[ResearchBar, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,open,high,low,close,volume"]
    for bar in bars:
        stamp = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=UTC).isoformat()
        lines.append(f"{stamp},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.unit
def test_twelve_template_fixture_pipeline_keeps_holdout_closed(tmp_path: Path) -> None:
    """Same 12 first-cycle templates on a fixture tape. Not the sealed NT8 holdout."""
    start = datetime(2023, 10, 28, tzinfo=UTC)
    end = datetime(2026, 1, 20, tzinfo=UTC)
    n = 480
    step = (end - start).total_seconds() / float(n - 1)
    mes_bars = tuple(
        _bar(
            datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC),
            open_=5000.0 + 0.01 * index,
            high=5000.5 + 0.01 * index,
            low=4999.5 + 0.01 * index,
            close=5000.0 + 0.01 * index,
        )
        for index in range(n)
    )
    mnq_bars = tuple(
        _bar(
            datetime.fromtimestamp(start.timestamp() + float(index) * step, tz=UTC),
            open_=18000.0 + 0.04 * index,
            high=18000.5 + 0.04 * index,
            low=17999.5 + 0.04 * index,
            close=18000.0 + 0.04 * index,
        )
        for index in range(n)
    )
    root = tmp_path / "data" / "research"
    _write_csv(root / "MES" / "1m" / "mes.csv", mes_bars)
    _write_csv(root / "MNQ" / "1m" / "mnq.csv", mnq_bars)
    clear_materialize_cache()
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=tmp_path,
        specs=first_cycle_specs(),
    )
    assert result.report.n_tested == 12
    assert result.report.holdout_seal_sha256 == ""
    assert result.report.holdout_eval == ()
    assert all(row.n_trades is not None for row in result.report.rows)
    assert all(row.n_trials is not None for row in result.report.rows)
    dest = Path("experiments/reports")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "phase5_p2_fixture_pipeline.json").write_text(
        (tmp_path / "reports" / "phase5_research_cycles.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    header = (
        "# Fixture-tape 12-template pipeline (NOT the sealed NT8 holdout)\n\n"
        "Real MES/MNQ CSVs were not mounted (`LUMINA_RESEARCH_DATA_DIR` unset). "
        "This table is the same 12 first-cycle templates on a synthetic train tape "
        "so diagnostics of the fixed pipeline are visible. Holdout eval is empty.\n\n"
    )
    (dest / "phase5_p2_fixture_pipeline.md").write_text(
        header + (tmp_path / "reports" / "phase5_p2_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_real_tape_rerun_is_blocked_without_research_data(tmp_path: Path) -> None:
    clear_materialize_cache()
    result = run_research_cycles(
        work_dir=tmp_path / "work",
        report_dir=tmp_path / "reports",
        evolution_log_dir=tmp_path / "evo",
        repo_root=Path("/workspace"),
        data_dir=tmp_path / "missing-research-data",
        specs=first_cycle_specs(),
    )
    assert result.report.stopped is True
    assert result.report.stop_reason == "no_usable_real_market_data"
    assert result.report.n_tested == 0
    assert all(row.n_trades is None for row in result.report.rows)
    dest = Path("experiments/reports")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "phase5_p2_real_rerun_blocked.json").write_text(
        (tmp_path / "reports" / "phase5_research_cycles.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (dest / "phase5_p2_real_rerun_blocked.md").write_text(
        "# Real NT8 12-template re-run blocked\n\n"
        "`LUMINA_RESEARCH_DATA_DIR` is unset and the NT8 CSVs are not in git. "
        "The sealed holdout was not opened. Re-run on the same 12 templates as soon "
        "as `MES_continuous_unadj_1m_2023-10-01_2026-10-29.csv` and the MNQ counterpart "
        "are mounted.\n\n" + (tmp_path / "reports" / "phase5_p2_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
