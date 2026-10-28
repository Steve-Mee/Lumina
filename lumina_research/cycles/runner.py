"""Pre-register economic hypotheses, then run the Validation Gate on real bars only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import HypothesisProposed, ValidationResult
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.cycles.catalog import EconomicCatalogGenerator, HypothesisSpec, catalog
from lumina_research.cycles.cost_bands import report_band
from lumina_research.cycles.data import DataStatus, discover_data, tape_for
from lumina_research.cycles.geometry import Geometry, require_geometry
from lumina_research.cycles.kill_rate import diagnose_kill_rate
from lumina_research.cycles.report import CycleReport, CycleRow, death_reason, write_cycle_reports
from lumina_research.cycles.sim_plan import write_sim_plan
from lumina_research.cycles.strategies import Tape, simulate
from lumina_research.proof.log import log_proof_event
from lumina_research.proof.runner import DEFAULT_EVOLUTION_LOG, DEFAULT_REPORTS
from lumina_research.validation.trial_registry import TrialRegistry

_REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class ResearchCycleResult:
    report: CycleReport
    json_path: Path
    md_path: Path
    data: DataStatus
    kill_rate: float | None
    kill_rate_flag: str


def run_research_cycles(
    *,
    work_dir: Path,
    report_dir: Path = DEFAULT_REPORTS,
    evolution_log_dir: Path | None = DEFAULT_EVOLUTION_LOG,
    data_dir: Path | None = None,
    repo_root: Path | None = None,
    seed: int = 20261028,
    specs: tuple[HypothesisSpec, ...] | None = None,
) -> ResearchCycleResult:
    """Pre-register template variants, then gate them on real data. No live/SIM orders."""
    work_dir.mkdir(parents=True, exist_ok=True)
    audit = work_dir / "audit.jsonl"
    log_path = work_dir / "experiments.jsonl"
    specs = specs if specs is not None else catalog()
    bus = EventBus()
    registry = TrialRegistry(audit)
    generator = EconomicCatalogGenerator(specs)
    hypothesis = HypothesisAgent(
        bus=bus,
        registry=registry,
        generators=(generator,),
        experiment_log_path=log_path,
    )
    status = discover_data(repo_root=repo_root if repo_root is not None else _REPO, data_dir=data_dir)
    geometries = _geometries(specs)
    validation: ValidationAgent | None = None
    if status.usable:
        validation = ValidationAgent(
            bus=bus,
            registry=registry,
            authority=ProvenanceAuthority(),
            experiment_log_path=log_path,
            audit_path=audit,
            materializer=_materializer(specs, status),
        )
    proposed = hypothesis.generate(seed=seed, counts=(len(specs),))
    if not status.usable or validation is None:
        report = _untested_report(proposed, specs, geometries, status)
        json_path, md_path = write_cycle_reports(report, report_dir)
        write_sim_plan(report_dir)
        log_proof_event(
            path=log_path,
            event="research_cycles",
            metrics={
                "n_hypotheses": report.n_hypotheses,
                "n_tested": 0,
                "kill_rate": None,
                "stopped": True,
                "stop_reason": report.stop_reason,
                "required": dict(status.required),
            },
            evolution_log_dir=evolution_log_dir,
            reject_reason="no_usable_real_market_data",
            failed_checks=("real_data",),
        )
        return ResearchCycleResult(
            report=report,
            json_path=json_path,
            md_path=md_path,
            data=status,
            kill_rate=None,
            kill_rate_flag="not_tested",
        )
    results = validation.flush()
    report = _tested_report(proposed, specs, geometries, status, results)
    json_path, md_path = write_cycle_reports(report, report_dir)
    write_sim_plan(report_dir)
    log_proof_event(
        path=log_path,
        event="research_cycles",
        metrics={
            "n_hypotheses": report.n_hypotheses,
            "n_tested": report.n_tested,
            "n_killed": report.n_killed,
            "n_survivors": report.n_survivors,
            "kill_rate": report.kill_rate,
            "kill_rate_flag": report.kill_rate_flag,
            "stopped": False,
            "cost_bands": [item.root for item in report.cost_bands],
        },
        evolution_log_dir=evolution_log_dir,
        reject_reason=None,
        failed_checks=(),
    )
    return ResearchCycleResult(
        report=report,
        json_path=json_path,
        md_path=md_path,
        data=status,
        kill_rate=report.kill_rate,
        kill_rate_flag=report.kill_rate_flag,
    )


def _geometries(specs: tuple[HypothesisSpec, ...]) -> tuple[Geometry, ...]:
    seen: dict[str, Geometry] = {}
    for spec in specs:
        if spec.instrument not in seen:
            floors = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
            seen[spec.instrument] = floors
    order = ("ES", "NQ", "MES", "MNQ")
    return tuple(seen[root] for root in order if root in seen)


def _materializer(specs: tuple[HypothesisSpec, ...], status: DataStatus) -> Callable[[HypothesisProposed], Tape]:
    by_id = {item.config_id: item for item in specs}

    def _map(hypothesis: HypothesisProposed) -> Tape:
        spec = by_id[hypothesis.config_id]
        tape = tape_for(status, spec.instrument)
        geometry = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
        return simulate(
            family=spec.family,
            bars=tape.bars,
            geometry=geometry,
            lookback=spec.lookback,
            threshold=spec.threshold,
            mode=spec.mode,
        )

    return _map


def _untested_report(
    proposed: tuple[HypothesisProposed, ...],
    specs: tuple[HypothesisSpec, ...],
    geometries: tuple[Geometry, ...],
    status: DataStatus,
) -> CycleReport:
    by_id = {item.config_id: item for item in specs}
    rows = tuple(_row(item, by_id[item.config_id], tested=False, result=None, stopped=True) for item in proposed)
    return CycleReport(
        n_hypotheses=len(rows),
        n_tested=0,
        n_killed=0,
        n_survivors=0,
        kill_rate=None,
        kill_rate_flag="not_tested",
        cost_bands=tuple(report_band(root) for root in ("ES", "NQ", "MES", "MNQ")),
        data=status,
        rows=rows,
        geometry_by_root=geometries,
        stopped=True,
        stop_reason="no_usable_real_market_data",
    )


def _tested_report(
    proposed: tuple[HypothesisProposed, ...],
    specs: tuple[HypothesisSpec, ...],
    geometries: tuple[Geometry, ...],
    status: DataStatus,
    results: tuple[ValidationResult, ...],
) -> CycleReport:
    by_id = {item.config_id: item for item in specs}
    by_hyp = {item.hypothesis_id: item for item in results}
    rows = tuple(
        _row(
            item,
            by_id[item.config_id],
            tested=item.hypothesis_id in by_hyp,
            result=by_hyp.get(item.hypothesis_id),
            stopped=False,
        )
        for item in proposed
    )
    n = len(rows)
    n_tested = sum(1 for item in rows if item.tested)
    n_killed = sum(1 for item in rows if item.tested and not item.passed)
    n_survived = sum(1 for item in rows if item.tested and item.passed)
    kill_rate = None if n_tested == 0 else n_killed / float(n_tested)
    return CycleReport(
        n_hypotheses=n,
        n_tested=n_tested,
        n_killed=n_killed,
        n_survivors=n_survived,
        kill_rate=kill_rate,
        kill_rate_flag=diagnose_kill_rate(
            kill_rate=kill_rate,
            n_hypotheses=n_tested,
            n_survivors=n_survived,
        ),
        cost_bands=tuple(report_band(root) for root in ("ES", "NQ", "MES", "MNQ")),
        data=status,
        rows=rows,
        geometry_by_root=geometries,
        stopped=False,
        stop_reason="",
    )


def _row(
    hypothesis: HypothesisProposed,
    spec: HypothesisSpec,
    *,
    tested: bool,
    result: ValidationResult | None,
    stopped: bool,
) -> CycleRow:
    geometry = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
    passed = bool(result.passed) if result is not None else False
    reasons = tuple(result.reject_reasons) if result is not None else ()
    pbo = None if result is None or result.pbo.pbo is None else float(result.pbo.pbo)
    dsr = None if result is None or result.dsr.probability is None else float(result.dsr.probability)
    wfe = None if result is None or result.wfe.wfe is None else float(result.wfe.wfe)
    median = None if result is None else result.median_oos_after_costs
    windows = None if result is None else result.n_oos_windows
    return CycleRow(
        hypothesis_id=hypothesis.hypothesis_id,
        config_id=spec.config_id,
        template_id=spec.template_id,
        family=spec.family,
        instrument=spec.instrument,
        pre_registered=True,
        tested=tested,
        passed=passed,
        reject_reasons=reasons,
        pbo=pbo,
        dsr=dsr,
        wfe=wfe,
        n_oos_windows=windows,
        median_oos=median,
        geometry=geometry,
        death_reason=death_reason(tested=tested, passed=passed, reasons=reasons, stopped=stopped),
    )
