"""Continuity runtime: admit sealed promotions, monitor decay, cap, scan, replenish."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Sequence

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    RESEARCH_VALIDATION_TOPIC,
    PromotionCandidate,
    ValidationResult,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.generators import NoiseGenerator, PlantedEdgeGenerator
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.promotion import PromotionAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.evolution.integrity import (
    IntegrityError,
    IntegritySnapshot,
    assert_intact,
    capture_integrity,
    refuse_protected_write,
)
from lumina_research.evolution.regime import RegimeAction, RegimePolicy
from lumina_research.monitoring.capacity import CapacityController
from lumina_research.monitoring.config import ContinuityConfig, load_default_config
from lumina_research.monitoring.guardian import GuardianAgent
from lumina_research.monitoring.monitor import LivePerformanceMonitor
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.replenish import ReplenishAgent
from lumina_research.monitoring.report import (
    DetectionPath,
    DetectionReport,
    GuardianReport,
    build_detection_report,
    log_decision,
    write_detection_reports,
    write_guardian_report,
)
from lumina_research.monitoring.sizing import ContinuitySizer
from lumina_research.monitoring.synthetic import (
    DEFAULT_OOS,
    decaying_path,
    healthy_path,
    oos_stats,
    seal_promotion_pair,
)
from lumina_research.monitoring.types import ContinuityRefused, Instrument, LiveSignal
from lumina_research.risk_core.config import load_default_config as load_risk_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import Decision
from lumina_research.validation.trial_registry import TrialRegistry

_INSTRUMENTS: dict[str, Instrument] = {"ES": "ES", "NQ": "NQ", "MES": "MES", "MNQ": "MNQ"}

DEFAULT_SEED = 20261028


class ContinuityIntegrityError(RuntimeError):
    """Protected surface drifted or a bypass was attempted."""


class ContinuityRuntime(Frozen):
    """Deterministic continuity processor. New signals still require the Validation Gate."""

    bus: EventBus
    registry: LiveSignalRegistry
    authority: ProvenanceAuthority
    config: ContinuityConfig
    monitor: LivePerformanceMonitor
    capacity: CapacityController
    guardian: GuardianAgent
    replenish: ReplenishAgent
    sizer: ContinuitySizer
    core: RiskCore
    hypothesis: HypothesisAgent
    validation: ValidationAgent
    promotion: PromotionAgent
    trials: TrialRegistry
    regime: RegimePolicy
    log_path: Path
    _evolution_log_dir: Path | None
    _snapshot: IntegritySnapshot

    def __init_subclass__(cls) -> None:
        raise TypeError("ContinuityRuntime cannot be subclassed")

    def __init__(
        self,
        *,
        audit_path: Path,
        experiment_log_path: Path,
        bus: EventBus | None = None,
        blackboard: AgentBlackboard | None = None,
        config: ContinuityConfig | None = None,
        evolution_log_dir: Path | None = None,
        equity: float | None = None,
    ) -> None:
        snapshot = capture_integrity()
        cfg = config if config is not None else load_default_config()
        core_equity = float(cfg.equity if equity is None else equity)
        if core_equity > float(cfg.equity) + 1e-9:
            raise ContinuityRefused("equity cannot exceed continuity config")
        event_bus = bus if bus is not None else EventBus()
        sealer = ProvenanceAuthority()
        registry = LiveSignalRegistry(authority=sealer, config=cfg)
        core = RiskCore(load_risk_config(), equity=core_equity)
        trials = TrialRegistry(audit_path)
        hypothesis = HypothesisAgent(
            bus=event_bus,
            registry=trials,
            generators=(
                NoiseGenerator(instrument="MES"),
                PlantedEdgeGenerator(instrument="MES", quantity=2.0, price=5_000.0),
            ),
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
        )
        validation = ValidationAgent(
            bus=event_bus,
            registry=trials,
            authority=sealer,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
            audit_path=audit_path,
            equity=core_equity,
        )
        promotion = PromotionAgent(
            bus=event_bus,
            core=core,
            authority=sealer,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
        )
        monitor = LivePerformanceMonitor(
            bus=event_bus,
            registry=registry,
            authority=sealer,
            config=cfg,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
            evolution_log_dir=evolution_log_dir,
        )
        capacity = CapacityController(
            bus=event_bus,
            registry=registry,
            authority=sealer,
            config=cfg,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
            evolution_log_dir=evolution_log_dir,
        )
        guardian = GuardianAgent(
            bus=event_bus,
            registry=registry,
            authority=sealer,
            config=cfg,
            experiment_log_path=experiment_log_path,
            blackboard=blackboard,
            evolution_log_dir=evolution_log_dir,
        )
        replenish = ReplenishAgent(
            bus=event_bus,
            registry=registry,
            authority=sealer,
            config=cfg,
            experiment_log_path=experiment_log_path,
            hypothesis=hypothesis,
            blackboard=blackboard,
            evolution_log_dir=evolution_log_dir,
        )
        self.bus = event_bus
        self.registry = registry
        self.authority = sealer
        self.config = cfg
        self.monitor = monitor
        self.capacity = capacity
        self.guardian = guardian
        self.replenish = replenish
        self.sizer = ContinuitySizer(core=core, registry=registry)
        self.core = core
        self.hypothesis = hypothesis
        self.validation = validation
        self.promotion = promotion
        self.trials = trials
        self.regime = RegimePolicy()
        self.log_path = experiment_log_path
        self._evolution_log_dir = evolution_log_dir
        self._snapshot = snapshot
        self._freeze()

    def assert_intact(self) -> IntegritySnapshot:
        try:
            assert_intact(self._snapshot)
        except IntegrityError as exc:
            raise ContinuityIntegrityError(str(exc)) from exc
        return capture_integrity()

    def insert_direct(self, signal: LiveSignal) -> None:
        self.registry.insert_direct(signal)

    def replenish_shortcut(self, signal_id: str) -> None:
        self.replenish.shortcut_admit(signal_id)

    def increase_weight(self, signal_id: str, weight: float) -> None:
        self.monitor.increase_weight(signal_id, weight)

    def set_risk_limits(self) -> None:
        self.guardian.set_risk_limits()

    def mutate_thresholds(self) -> None:
        raise ContinuityRefused("threshold mutation requires ADR plus signed human review")

    def write_risk_core(self, path: Path) -> None:
        try:
            refuse_protected_write(path)
        except IntegrityError as exc:
            raise ContinuityRefused(str(exc)) from exc

    def admit(self, candidate: PromotionCandidate, validation: ValidationResult) -> LiveSignal:
        self.assert_intact()
        signal = self.registry.admit(candidate, validation)
        self._log_admit(signal)
        return signal

    def ingest_promotions(self) -> tuple[LiveSignal, ...]:
        self.assert_intact()
        validations: dict[str, ValidationResult] = {}
        for event in self.bus.history(RESEARCH_VALIDATION_TOPIC, limit=10_000):
            parsed = event.typed_payload(ValidationResult)
            validations[parsed.hypothesis_id] = parsed
        admitted: list[LiveSignal] = []
        live = {item.signal_id for item in self.registry.signals()}
        for candidate in self.promotion.issued():
            if candidate.hypothesis_id in live:
                continue
            validation = validations.get(candidate.hypothesis_id)
            if validation is None:
                raise ContinuityRefused("promotion without ValidationResult")
            signal = self.registry.admit(candidate, validation)
            self._log_admit(signal)
            admitted.append(signal)
            live.add(candidate.hypothesis_id)
        return tuple(admitted)

    def _log_admit(self, signal: LiveSignal) -> None:
        log_decision(
            path=self.log_path,
            agent_id="live_registry",
            event="admit",
            signal_id=signal.signal_id,
            metrics={
                "stage": signal.stage,
                "weight": signal.weight,
                "capacity_scale": signal.capacity_scale,
                "instrument": signal.instrument,
                "n_oos_windows": signal.n_oos_windows,
                "oos_values": len(signal.oos_values),
                "base_quantity": signal.base_quantity,
                "base_notional": signal.base_notional,
                "admission_mac": signal.admission_mac,
                "state_mac": signal.state_mac,
            },
            evolution_log_dir=self._evolution_log_dir,
        )

    def observe(self, signal_id: str, metric: float) -> LiveSignal:
        self.assert_intact()
        return self.monitor.observe(signal_id, metric)

    def rebalance(self) -> tuple[LiveSignal, ...]:
        self.assert_intact()
        return self.capacity.rebalance()

    def propose_order(
        self,
        signal_id: str,
        *,
        quantity: float,
        price: float,
        regime: RegimeAction | None = None,
    ) -> Decision:
        self.assert_intact()
        return self.sizer.propose(signal_id, quantity=quantity, price=price, regime=regime)

    def request_replenishment(self, *, seed: int) -> tuple[LiveSignal, ...]:
        self.assert_intact()
        planted = min(2, self.config.replenish_count)
        noise = max(0, self.config.replenish_count - planted)
        result = self.replenish.maybe_request(seed=seed, counts=(noise, planted))
        if result is None:
            return ()
        self.validation.flush()
        return self.ingest_promotions()

    def guardian_scan(
        self,
        cadence: str,
        *,
        decisions: Sequence[dict[str, object]] = (),
        report_dir: Path | None = None,
    ) -> GuardianReport:
        self.assert_intact()
        if cadence not in {"daily", "weekly"}:
            raise ContinuityRefused("cadence must be daily or weekly")
        label: str = cadence
        report = self.guardian.scan(
            cadence="daily" if label == "daily" else "weekly",
            baseline=self._snapshot,
            trials=self.trials.records(),
            decisions=decisions,
        )
        for signal_id in report.suspend_proposals:
            if self.registry.get(signal_id) is not None:
                self.monitor.apply_guardian_suspend(signal_id, reason=f"guardian:{cadence}")
        if report_dir is not None:
            write_guardian_report(report, report_dir)
        return report


def run_phase4_detection(
    *,
    audit_path: Path,
    experiment_log_path: Path,
    n_healthy: int = 20,
    n_decaying: int = 20,
    n_days: int = 70,
    decay_start: int = 20,
    seed: int = DEFAULT_SEED,
    report_dir: Path | None = None,
    instrument: str = "MES",
) -> DetectionReport:
    runtime = ContinuityRuntime(audit_path=audit_path, experiment_log_path=experiment_log_path)
    rng = random.Random(seed)
    oos = DEFAULT_OOS
    mean, stdev = oos_stats(oos)
    paths: list[DetectionPath] = []
    mapped = _INSTRUMENTS.get(instrument.strip().upper())
    if mapped is None:
        raise ContinuityRefused(f"unknown instrument {instrument!r}")
    inst = mapped
    trial = 1
    for index in range(n_healthy):
        hyp = f"hyp-healthy-{index}"
        candidate, validation = seal_promotion_pair(
            runtime.authority,
            hypothesis_id=hyp,
            config_id=hyp,
            trial_id=trial,
            instrument=inst,
            quantity=2.0,
            notional=10_000.0,
            oos=oos,
        )
        trial += 1
        runtime.admit(candidate, validation)
        series = healthy_path(rng, oos_mean=mean, oos_stdev=stdev, n=n_days)
        for metric in series:
            runtime.observe(hyp, metric)
        signal = runtime.registry.require(hyp)
        false_alarm = signal.stage != "active"
        paths.append(
            DetectionPath(
                signal_id=hyp,
                decaying=False,
                detected=False,
                false_alarm=false_alarm,
                time_to_detect=None,
                final_stage=signal.stage,
                kind="healthy",
            )
        )
    for index in range(n_decaying):
        hyp = f"hyp-decay-{index}"
        candidate, validation = seal_promotion_pair(
            runtime.authority,
            hypothesis_id=hyp,
            config_id=hyp,
            trial_id=trial,
            instrument=inst,
            quantity=2.0,
            notional=10_000.0,
            oos=oos,
        )
        trial += 1
        runtime.admit(candidate, validation)
        series = decaying_path(rng, oos_mean=mean, oos_stdev=stdev, n=n_days, decay_start=decay_start)
        detect_day: int | None = None
        for day, metric in enumerate(series):
            updated = runtime.observe(hyp, metric)
            if detect_day is None and updated.stage != "active":
                detect_day = max(0, day - decay_start)
        signal = runtime.registry.require(hyp)
        paths.append(
            DetectionPath(
                signal_id=hyp,
                decaying=True,
                detected=signal.stage != "active",
                false_alarm=False,
                time_to_detect=detect_day,
                final_stage=signal.stage,
                kind="abrupt_decay",
            )
        )
    report = build_detection_report(seed=seed, paths=paths)
    if report_dir is not None:
        write_detection_reports(report, report_dir)
    return report
