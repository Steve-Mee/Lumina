"""Birth → reflector propose → governance → Phase 2 Validation Gate → PromotionCandidate."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    HypothesisProposed,
    MutationProposed,
    PromotionCandidate,
    ValidationResult,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.promotion import PromotionAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.evolution.birth import BirthPhase
from lumina_research.evolution.governance import GovernanceGate, ReviewAuthority
from lumina_research.evolution.integrity import (
    IntegrityError,
    IntegritySnapshot,
    assert_intact,
    capture_integrity,
    refuse_protected_write,
)
from lumina_research.evolution.mutations import DraftGenerator, mutation_to_draft
from lumina_research.evolution.reflector import ReflectorAgent
from lumina_research.evolution.regime import RegimeObservation, RegimePolicy
from lumina_research.evolution.report import (
    EvolutionReport,
    MultiSeedEvolutionReport,
    SeedEvolution,
    build_evolution_report,
    write_evolution_reports,
    write_multiseed_evolution_reports,
)
from lumina_research.evolution.seal import mutation_fingerprint
from lumina_research.evolution.types import Instrument, default_parent
from lumina_research.fitness import FitnessRefused, compute_fitness
from lumina_research.risk_core.config import load_default_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.validation.trial_registry import TrialRegistry

DEFAULT_SEED = 20261028
DEFAULT_N_NOISE = 2
DEFAULT_N_OVERFIT = 0
DEFAULT_MULTISEED_N_NOISE = 26
DEFAULT_MULTISEED_N_OVERFIT = 2
DEFAULT_MULTISEED_SEEDS: tuple[int, ...] = (20261028, 7, 13, 21, 42, 99, 123, 256, 1024, 4096)
DEFAULT_MULTISEED_INSTRUMENTS: tuple[Instrument, ...] = (
    "MES",
    "MNQ",
    "ES",
    "NQ",
    "MES",
    "MNQ",
    "ES",
    "NQ",
    "MES",
    "MNQ",
)
_ADR_DEFAULT = Path(__file__).resolve().parents[2] / "docs" / "adr"


class EvolutionIntegrityError(RuntimeError):
    """Bypass, monkeypatch, or protected-surface drift."""


class EvolutionRuntime(Frozen):
    """Deterministic processor. Agents propose; this object never skips the gate."""

    bus: EventBus
    registry: TrialRegistry
    authority: ProvenanceAuthority
    reviews: ReviewAuthority
    reflector: ReflectorAgent
    governance: GovernanceGate
    validation: ValidationAgent
    promotion: PromotionAgent
    birth: BirthPhase
    regime: RegimePolicy
    log_path: Path
    blackboard: AgentBlackboard | None
    _snapshot: IntegritySnapshot
    _bound_evaluate: object
    _bound_record: object

    def __init_subclass__(cls) -> None:
        raise TypeError("EvolutionRuntime cannot be subclassed")

    def __init__(
        self,
        *,
        audit_path: Path,
        experiment_log_path: Path,
        adr_root: Path | None = None,
        bus: EventBus | None = None,
        blackboard: AgentBlackboard | None = None,
        equity: float = 100_000.0,
        review_key: bytes | None = None,
    ) -> None:
        snapshot = capture_integrity()
        event_bus = bus if bus is not None else EventBus()
        registry = TrialRegistry(audit_path)
        authority = ProvenanceAuthority()
        reviews = ReviewAuthority(key=review_key)
        core = RiskCore(load_default_config(), equity=equity)
        reflector = ReflectorAgent(
            bus=event_bus,
            registry=registry,
            authority=authority,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
        )
        governance = GovernanceGate(
            bus=event_bus,
            authority=authority,
            reviews=reviews,
            registry=registry,
            experiment_log_path=experiment_log_path,
            adr_root=adr_root if adr_root is not None else _ADR_DEFAULT,
            blackboard=blackboard,
        )
        validation = ValidationAgent(
            bus=event_bus,
            registry=registry,
            authority=authority,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
            audit_path=audit_path,
            equity=equity,
        )
        promotion = PromotionAgent(
            bus=event_bus,
            core=core,
            authority=authority,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
        )
        self.bus = event_bus
        self.registry = registry
        self.authority = authority
        self.reviews = reviews
        self.reflector = reflector
        self.governance = governance
        self.validation = validation
        self.promotion = promotion
        self.birth = BirthPhase(reflector)
        self.regime = RegimePolicy()
        self.log_path = experiment_log_path
        self.blackboard = blackboard
        self._snapshot = snapshot
        self._bound_evaluate = object.__getattribute__(validation, "_evaluate")
        self._bound_record = TrialRegistry.record
        self._freeze()

    def assert_intact(self) -> IntegritySnapshot:
        try:
            assert_intact(self._snapshot)
        except IntegrityError as exc:
            raise EvolutionIntegrityError(str(exc)) from exc
        if object.__getattribute__(self.validation, "_evaluate") is not self._bound_evaluate:
            raise EvolutionIntegrityError("evaluate_candidate rebound")
        if "record" in object.__getattribute__(self.registry, "__dict__"):
            raise EvolutionIntegrityError("trial counting skipped")
        if object.__getattribute__(type(self.registry), "record") is not self._bound_record:
            raise EvolutionIntegrityError("trial counting skipped")
        return capture_integrity()

    def promote_direct(self, candidate: PromotionCandidate) -> None:
        del candidate
        raise EvolutionIntegrityError("direct promotion is forbidden")

    def skip_trials(self) -> None:
        raise EvolutionIntegrityError("every mutation must be counted in TrialRegistry")

    def write_protected(self, path: Path) -> None:
        refuse_protected_write(path)

    def process(
        self,
        mutations: Sequence[MutationProposed],
        *,
        seed: int,
        regime_obs: RegimeObservation | None = None,
        report_dir: Path | None = None,
    ) -> EvolutionReport:
        self.assert_intact()
        self._require_registered(mutations)
        n_start = self.registry.n_trials
        if n_start < len(mutations):
            raise EvolutionIntegrityError("trial counting skipped")
        observation = regime_obs if regime_obs is not None else RegimeObservation(vol="low", trend="up")
        action = self.regime.act(observation)
        admitted: list[MutationProposed] = []
        for mutation in mutations:
            decision = self.governance.admit(mutation)
            if decision.applied:
                raise EvolutionIntegrityError("evolution applied a protected change")
            if decision.admitted:
                admitted.append(mutation)
        self.assert_intact()
        generated: tuple[HypothesisProposed, ...] = ()
        results: tuple[ValidationResult, ...] = ()
        if admitted:
            drafts = tuple(mutation_to_draft(item, action=action) for item in admitted)
            hypothesis = HypothesisAgent(
                bus=self.bus,
                registry=self.registry,
                generators=(DraftGenerator(drafts),),
                experiment_log_path=self.log_path,
                blackboard=self.blackboard,
            )
            generated = hypothesis.generate(seed=seed, counts=(len(drafts),))
            results = self.validation.flush()
        self.assert_intact()
        n_end = self.registry.n_trials
        if admitted and n_end <= n_start:
            raise EvolutionIntegrityError("trial counting skipped")
        planted_flags = {item.hypothesis_id: item.planted for item in generated}
        self._verify_fitness()
        snap = self.assert_intact()
        report = build_evolution_report(
            seed=seed,
            mutations=mutations,
            decisions=self.governance.decisions(),
            results=results,
            promotions=self.promotion.issued(),
            planted_flags=planted_flags,
            n_trials_start=n_start,
            n_trials_end=n_end,
            floors_intact=snap.floors == self._snapshot.floors,
            risk_core_intact=(
                snap.live_risk_hash == self._snapshot.live_risk_hash
                and snap.research_risk_hash == self._snapshot.research_risk_hash
            ),
        )
        if report_dir is not None:
            write_evolution_reports(report, report_dir)
        return report

    def _require_registered(self, mutations: Sequence[MutationProposed]) -> None:
        records = {item.trial_id: item for item in self.registry.records()}
        for mutation in mutations:
            record = records.get(mutation.trial_id)
            if record is None or record.config_id != mutation.config_id:
                raise EvolutionIntegrityError("trial counting skipped")
            expected = mutation_fingerprint(
                config_id=mutation.config_id,
                kind=mutation.kind,
                target=mutation.target,
                genome=mutation.genome.model_dump(mode="json"),
                parent_config_id=mutation.parent_config_id,
            )
            if record.metrics.get("mutation_sha256") != expected:
                raise EvolutionIntegrityError("trial counting skipped")

    def _verify_fitness(self) -> None:
        for evaluation in self.validation.evaluations():
            if evaluation.passed and evaluation.fitness is None:
                raise EvolutionIntegrityError("gate pass without composite fitness")
            if evaluation.fitness is None:
                continue
            try:
                recomputed = compute_fitness(evaluation.report, turnover=evaluation.turnover)
            except FitnessRefused as exc:
                raise EvolutionIntegrityError("fitness swapped") from exc
            if recomputed.value != evaluation.fitness.value:
                raise EvolutionIntegrityError("fitness swapped")


def run_phase3_evolution(
    *,
    audit_path: Path,
    experiment_log_path: Path,
    n_noise: int = DEFAULT_N_NOISE,
    n_overfit: int = DEFAULT_N_OVERFIT,
    seed: int = DEFAULT_SEED,
    instrument: Instrument = "MES",
    report_dir: Path | None = None,
    adr_root: Path | None = None,
    equity: float = 100_000.0,
    open_oos_size: int | None = None,
) -> EvolutionReport:
    """Open a window, tune the parent, add overfit and noise children, run the full Phase 2 gate."""
    runtime = EvolutionRuntime(
        audit_path=audit_path,
        experiment_log_path=experiment_log_path,
        adr_root=adr_root,
        equity=equity,
    )
    parent = default_parent(instrument=instrument)
    mutations = [
        runtime.birth.open_window(parent, seed=seed, index=0, oos_size=open_oos_size),
        runtime.birth.tune(parent, seed=seed + 1, index=1, scale_mu=0.95),
    ]
    for offset in range(n_overfit):
        mutations.append(
            runtime.birth.overfit_tune(parent, seed=seed + 5 + offset, index=5 + offset, scale_mu=1.8 + 0.1 * offset)
        )
    for offset in range(n_noise):
        mutations.append(runtime.birth.noise_child(parent, seed=seed + 10 + offset, index=10 + offset))
    return runtime.process(tuple(mutations), seed=seed, report_dir=report_dir)


def run_multiseed_evolution(
    *,
    audit_dir: Path,
    experiment_log_dir: Path,
    n_noise: int = DEFAULT_N_NOISE,
    n_overfit: int = DEFAULT_N_OVERFIT,
    seeds: Sequence[int] = DEFAULT_MULTISEED_SEEDS,
    instruments: Sequence[Instrument] = DEFAULT_MULTISEED_INSTRUMENTS,
    report_dir: Path | None = None,
    equity: float = 100_000.0,
) -> MultiSeedEvolutionReport:
    if len(seeds) != len(instruments):
        raise ValueError("seeds and instruments must align")
    rows: list[SeedEvolution] = []
    for seed, instrument in zip(seeds, instruments, strict=True):
        report = run_phase3_evolution(
            audit_path=audit_dir / f"audit-{seed}-{instrument}.jsonl",
            experiment_log_path=experiment_log_dir / f"exp-{seed}-{instrument}.jsonl",
            n_noise=n_noise,
            n_overfit=n_overfit,
            seed=int(seed),
            instrument=instrument,
            equity=equity,
        )
        rows.append(SeedEvolution(seed=int(seed), instrument=instrument, report=report))
    combined = MultiSeedEvolutionReport.from_seeds(tuple(rows))
    if report_dir is not None:
        write_multiseed_evolution_reports(combined, report_dir)
    return combined
