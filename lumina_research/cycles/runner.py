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
from lumina_research.cycles.catalog import EconomicCatalogGenerator, HypothesisSpec
from lumina_research.cycles.cost_bands import report_band
from lumina_research.cycles.data import MIN_BARS, DataStatus, discover_data, tape_for
from lumina_research.cycles.data_spec import write_data_spec
from lumina_research.cycles.first_cycle import first_cycle_specs, write_first_cycle_preregister
from lumina_research.cycles.holdout import HoldoutLocked, P2_HOLDOUT_START_NS, P2_PIN_MIN_BARS, access_bars
from lumina_research.cycles.geometry import Geometry, require_geometry
from lumina_research.cycles.independence import IndependenceRow, select_independent
from lumina_research.cycles.kill_rate import diagnose_kill_rate
from lumina_research.cycles.manifest import write_data_manifest
from lumina_research.cycles.daily import unique_sessions
from lumina_research.cycles.p2_cycle import (
    DAILY_RESAMPLE_MIN_BARS,
    HoldoutEvalRow,
    evaluate_holdout,
    materialize_spec,
    pin_tape,
    prepare_for_purpose,
    window_note,
    with_walk_forward_sizes,
)
from lumina_research.cycles.prepare import PreparedTape
from lumina_research.cycles.report import CycleReport, CycleRow, death_reason, write_cycle_reports
from lumina_research.cycles.seal import CSV_SHA256, file_sha256, load_seal, seal_holdout
from lumina_research.cycles.sim_plan import write_sim_plan
from lumina_research.cycles.strategies import Tape
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
    write_data_spec(report_dir)
    write_first_cycle_preregister(report_dir)
    specs = specs if specs is not None else first_cycle_specs()
    root = repo_root if repo_root is not None else _REPO
    status = discover_data(repo_root=root, data_dir=data_dir)
    seal_sha = ""
    prepared: dict[str, PreparedTape] = {}
    holdout_prepared: dict[str, PreparedTape] = {}
    if _is_real_p2(status):
        p2_tapes = tuple(pin_tape(item) for item in status.tapes if item.instrument in {"MES", "MNQ"})
        sealed = seal_holdout(p2_tapes, report_dir=report_dir, require_known_files=True)
        checked = load_seal(report_dir)
        if checked.get("holdout_start_ns") != P2_HOLDOUT_START_NS:
            raise HoldoutLocked("holdout seal drifted from 2026-01-29 after write")
        seal_sha = str(sealed.get("seal_sha256", ""))
        prepared = {item.instrument: prepare_for_purpose(item, purpose="gate") for item in p2_tapes}
        dropped = {key: value.dropped for key, value in prepared.items()}
        write_data_manifest(p2_tapes, repo_root=root, dropped=dropped)
        holdout_prepared = {item.instrument: prepare_for_purpose(item, purpose="evaluation") for item in p2_tapes}
        specs = with_walk_forward_sizes(specs, prepared)
    elif status.usable and _usable_for_gate(status):
        prepared = _prepare_map(specs, status, purpose="gate")
        specs = with_walk_forward_sizes(specs, prepared)
        holdout_prepared = _prepare_map(specs, status, purpose="evaluation")
    bus = EventBus()
    registry = TrialRegistry(audit)
    generator = EconomicCatalogGenerator(specs)
    hypothesis = HypothesisAgent(
        bus=bus,
        registry=registry,
        generators=(generator,),
        experiment_log_path=log_path,
    )
    geometries = _geometries(specs)
    validation: ValidationAgent | None = None
    if prepared:
        validation = ValidationAgent(
            bus=bus,
            registry=registry,
            authority=ProvenanceAuthority(),
            experiment_log_path=log_path,
            audit_path=audit,
            materializer=_materializer(specs, prepared),
        )
    proposed = hypothesis.generate(seed=seed, counts=(len(specs),))
    if not status.usable or validation is None or not prepared:
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
    independence = _independence(specs, results, prepared)
    report = _tested_report(
        proposed,
        specs,
        geometries,
        status,
        results,
        holdout_seal_sha256=seal_sha,
        wf_note=window_note(specs),
        independence=independence,
        holdout_eval=_holdout_rows(specs, results, holdout_prepared, independence=independence),
    )
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


def _usable_for_gate(status: DataStatus) -> bool:
    for tape in status.tapes:
        try:
            # access_bars(tape, purpose="gate") — train only; pin_tape locks 2026-01-29 on real P2.
            bars = access_bars(pin_tape(tape), purpose="gate")
        except HoldoutLocked:
            continue
        if len(bars) >= MIN_BARS:
            return True
    return False


def _is_real_p2(status: DataStatus) -> bool:
    by_root = {item.instrument: item for item in status.tapes}
    mes = by_root.get("MES")
    mnq = by_root.get("MNQ")
    if mes is None or mnq is None:
        return False
    if len(mes.bars) < P2_PIN_MIN_BARS or len(mnq.bars) < P2_PIN_MIN_BARS:
        return False
    for tape in (mes, mnq):
        expected = CSV_SHA256.get(tape.instrument)
        if expected is None or not tape.path.is_file():
            return False
        if file_sha256(tape.path) != expected:
            return False
    return True


def _prepare_map(
    specs: tuple[HypothesisSpec, ...],
    status: DataStatus,
    *,
    purpose: str,
) -> dict[str, PreparedTape]:
    prepared: dict[str, PreparedTape] = {}
    for spec in specs:
        if spec.instrument in prepared:
            continue
        try:
            tape = tape_for(status, spec.instrument)
        except Exception:
            continue
        try:
            prepared[spec.instrument] = prepare_for_purpose(pin_tape(tape), purpose=purpose)
        except (HoldoutLocked, ValueError):
            continue
    return prepared


def _geometries(specs: tuple[HypothesisSpec, ...]) -> tuple[Geometry, ...]:
    seen: dict[str, Geometry] = {}
    for spec in specs:
        if spec.instrument not in seen:
            floors = require_geometry(root=spec.instrument, target_ticks=spec.target_ticks, stop_ticks=spec.stop_ticks)
            seen[spec.instrument] = floors
    order = ("ES", "NQ", "MES", "MNQ")
    return tuple(seen[root] for root in order if root in seen)


def _materializer(
    specs: tuple[HypothesisSpec, ...],
    prepared: dict[str, PreparedTape],
) -> Callable[[HypothesisProposed], Tape]:
    by_id = {item.config_id: item for item in specs}
    cache: dict[str, Tape] = {}

    def _map(hypothesis: HypothesisProposed) -> Tape:
        spec = by_id[hypothesis.config_id]
        if spec.config_id in cache:
            return cache[spec.config_id]
        tape = prepared[spec.instrument]
        built = materialize_spec(spec, tape)
        cache[spec.config_id] = built
        return built

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
    *,
    holdout_seal_sha256: str = "",
    wf_note: str = "",
    independence: tuple[IndependenceRow, ...] = (),
    holdout_eval: tuple[HoldoutEvalRow, ...] = (),
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
        holdout_seal_sha256=holdout_seal_sha256,
        wf_note=wf_note,
        independence=independence,
        holdout_eval=holdout_eval,
    )


def _independence(
    specs: tuple[HypothesisSpec, ...],
    results: tuple[ValidationResult, ...],
    prepared: dict[str, PreparedTape],
) -> tuple[IndependenceRow, ...]:
    by_id = {item.config_id: item for item in specs}
    survivors = [item for item in results if item.passed and item.config_id in by_id]
    if len(survivors) < 1:
        return ()
    mapped: list[dict[object, float]] = []
    for item in survivors:
        spec = by_id[item.config_id]
        tape = prepared[spec.instrument]
        net = materialize_spec(spec, tape)[0]
        keys: tuple[object, ...]
        if len(tape.bars) >= DAILY_RESAMPLE_MIN_BARS:
            keys = unique_sessions(tape.session_dates)
        else:
            keys = tuple(range(len(net)))
        mapped.append(dict(zip(keys, net, strict=False)))
    common: set[object] | None = None
    for row in mapped:
        common = set(row) if common is None else common & set(row)
    ordered = tuple(sorted(common, key=str)) if common else ()
    series = tuple(tuple(row[key] for key in ordered) for row in mapped)
    scores = tuple(
        (0.0 if row.pbo.pbo is None else -float(row.pbo.pbo))
        + (0.0 if row.dsr.probability is None else float(row.dsr.probability))
        for row in survivors
    )
    return select_independent(
        config_ids=tuple(item.config_id for item in survivors),
        families=tuple(by_id[item.config_id].family for item in survivors),
        series=series,
        scores=scores,
    )


def _holdout_rows(
    specs: tuple[HypothesisSpec, ...],
    results: tuple[ValidationResult, ...],
    holdout_prepared: dict[str, PreparedTape],
    *,
    independence: tuple[IndependenceRow, ...],
) -> tuple[HoldoutEvalRow, ...]:
    by_id = {item.config_id: item for item in specs}
    filtered = bool(independence)
    kept = {item.config_id for item in independence if item.kept}
    rows: list[HoldoutEvalRow] = []
    for item in results:
        if not item.passed or item.config_id not in by_id:
            continue
        if filtered and item.config_id not in kept:
            continue
        spec = by_id[item.config_id]
        prepared = holdout_prepared.get(spec.instrument)
        if prepared is None:
            continue
        rows.append(evaluate_holdout(spec, prepared))
    return tuple(rows)


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
