"""Compact fail-closed battery used to kill monitoring mutants. No pytest."""

from __future__ import annotations

import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import MONITOR_AGENT_ID, RESEARCH_DECAY_TOPIC
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.integrity import capture_integrity
from lumina_research.monitoring.capacity import CapacityController
from lumina_research.monitoring.config import ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.guardian import GuardianAgent
from lumina_research.monitoring.loop import ContinuityIntegrityError, ContinuityRuntime
from lumina_research.monitoring.monitor import LivePerformanceMonitor
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.replenish import ReplenishAgent
from lumina_research.monitoring.sizing import ContinuitySizer
from lumina_research.monitoring.statistics import assess_decay
from lumina_research.monitoring.synthetic import DEFAULT_OOS, seal_promotion_pair
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.risk_core.config import load_default_config as load_risk_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import DecisionKind


def _refuse(exc: type[BaseException], fn: object, *args: object, **kwargs: object) -> None:
    try:
        if callable(fn):
            fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def _admit(
    runtime: ContinuityRuntime,
    hyp: str,
    trial: int,
    *,
    instrument: str = "MES",
    quantity: float = 2.0,
    notional: float = 10_000.0,
) -> None:
    mapped = "MES" if instrument == "MES" else "ES" if instrument == "ES" else "NQ" if instrument == "NQ" else "MNQ"
    candidate, validation = seal_promotion_pair(
        runtime.authority,
        hypothesis_id=hyp,
        config_id=hyp,
        trial_id=trial,
        instrument=mapped,
        quantity=quantity,
        notional=notional,
    )
    runtime.admit(candidate, validation)


def run() -> None:
    cfg = load_default_config()
    raw = asdict(cfg)
    raw["z_deweight"] = -100.0
    raw["z_suspend"] = -100.0
    raw["z_retire"] = -100.0
    _refuse(ContinuityConfigError, config_from_mapping, raw)
    bloated = asdict(cfg)
    bloated["equity"] = 1_000_000_000.0
    _refuse(ContinuityConfigError, config_from_mapping, bloated)
    long_window = asdict(cfg)
    long_window["window"] = 250
    _refuse(ContinuityConfigError, config_from_mapping, long_window)
    fat_cap = asdict(cfg)
    fat_cap["max_signal_notional_pct"] = 1.0
    _refuse(ContinuityConfigError, config_from_mapping, fat_cap)
    sprt = asdict(cfg)
    sprt["sprt_alpha"] = 0.20
    _refuse(ContinuityConfigError, config_from_mapping, sprt)

    quiet = assess_decay(tuple(0.8 for _ in range(30)), DEFAULT_OOS, cfg)
    if quiet.ready is not True or quiet.severity != 0:
        raise AssertionError("healthy window must stay active")
    loud = assess_decay(tuple(-1.0 for _ in range(30)), DEFAULT_OOS, cfg)
    if loud.severity < 1:
        raise AssertionError("obvious decay must be detected")
    short_window = assess_decay((0.8, 0.8), DEFAULT_OOS, cfg)
    if short_window.ready is True:
        raise AssertionError("short window must not be ready")

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        authority = ProvenanceAuthority()
        registry = LiveSignalRegistry(authority=authority, config=cfg)
        _refuse(ContinuityRefused, registry.increase_weight, "x", 2.0)
        _refuse(ContinuityRefused, registry.restore, "x")
        _refuse(ContinuityRefused, registry.insert_direct, None)

        candidate, validation = seal_promotion_pair(
            authority,
            hypothesis_id="hyp-k",
            config_id="hyp-k",
            trial_id=1,
            instrument="MES",
            quantity=2.0,
            notional=10_000.0,
            oos=(0.8, 0.81),
            n_oos_windows=6,
        )
        _refuse(ContinuityRefused, registry.admit, candidate, validation)

        candidate_ok, validation_ok = seal_promotion_pair(
            authority,
            hypothesis_id="hyp-ok",
            config_id="hyp-ok",
            trial_id=2,
            instrument="MES",
            quantity=2.0,
            notional=10_000.0,
        )
        signal = registry.admit(candidate_ok, validation_ok)
        if signal.weight != 1.0 or signal.stage != "active" or not registry.verify(signal):
            raise AssertionError("admit must seal an active signal")
        _refuse(ContinuityRefused, registry.insert, signal)
        lowered = registry.apply_stage("hyp-ok", "deweighted")
        if lowered.weight >= signal.weight or lowered.stage != "deweighted":
            raise AssertionError("deweight must reduce weight")
        _refuse(ContinuityRefused, registry.apply_capacity_scale, "hyp-ok", 1.5)
        scaled = registry.apply_capacity_scale("hyp-ok", 0.4)
        if scaled.capacity_scale > 0.4 + 1e-12:
            raise AssertionError("capacity scale must drop")
        _refuse(ContinuityRefused, registry.apply_capacity_scale, "hyp-ok", 0.9)
        retired = registry.apply_stage("hyp-ok", "retired")
        if retired.weight != 0.0 or retired.stage != "retired":
            raise AssertionError("retire must zero weight")
        zombie = replace(retired, stage="active", weight=1.0)
        if registry.verify(zombie) is not False:
            raise AssertionError("un-retire without state MAC must fail verify")

        bus = EventBus()
        log = root / "exp.jsonl"
        monitor = LivePerformanceMonitor(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        _refuse(ContinuityRefused, monitor.observe, "hyp-ok", float("nan"))
        _refuse(ContinuityRefused, monitor.observe, "hyp-ok", math.inf)

        candidate_b, validation_b = seal_promotion_pair(
            authority,
            hypothesis_id="hyp-sz",
            config_id="hyp-sz",
            trial_id=3,
            instrument="MES",
            quantity=2.0,
            notional=10_000.0,
        )
        registry.admit(candidate_b, validation_b)
        sizer = ContinuitySizer(core=RiskCore(load_risk_config(), equity=cfg.equity), registry=registry)
        now = datetime.now(timezone.utc)
        _refuse(ContinuityRefused, sizer.propose, "hyp-sz", quantity=9.0, price=100.0, at=now)
        _refuse(ContinuityRefused, sizer.propose, "hyp-sz", quantity=2.0, price=10_000.0, at=now)
        ok = sizer.propose("hyp-sz", quantity=2.0, price=5_000.0, at=now)
        if ok.kind is DecisionKind.APPROVED and ok.quantity > 2.0 + 1e-9:
            raise AssertionError("sizer must not exceed base quantity")

        capacity = CapacityController(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        _refuse(ContinuityRefused, capacity.scale_up, "hyp-sz", 1.0)

        guardian = GuardianAgent(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        _refuse(ContinuityRefused, guardian.set_risk_limits)
        missing_trials = guardian.scan(cadence="daily", baseline=capture_integrity(), trials=())
        if missing_trials.n_violations < 1:
            raise AssertionError("missing trial log must violate")

        replenish = ReplenishAgent(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        _refuse(ContinuityRefused, replenish.shortcut_admit, "hyp-fake")

        runtime = ContinuityRuntime(audit_path=root / "audit.jsonl", experiment_log_path=log)
        _refuse(ContinuityRefused, runtime.insert_direct, signal)
        _refuse(ContinuityRefused, runtime.mutate_thresholds)
        _refuse(ContinuityRefused, runtime.write_risk_core, root / "limits.toml")
        _refuse(ContinuityRefused, runtime.set_risk_limits)
        _refuse(ContinuityRefused, ContinuityRuntime, audit_path=root / "a2.jsonl", experiment_log_path=log, equity=1e9)

        _admit(runtime, "hyp-live", 1)
        live = runtime.registry.require("hyp-live")
        if not runtime.registry.verify(live):
            raise AssertionError("runtime admit must verify")
        mean = sum(DEFAULT_OOS) / len(DEFAULT_OOS)
        staged = False
        for _ in range(40):
            updated = runtime.observe("hyp-live", mean - 0.8)
            if updated.stage != "active":
                staged = True
                if updated.weight >= 1.0:
                    raise AssertionError("decay must reduce weight")
                break
        if not staged:
            raise AssertionError("abrupt decay must de-weight")
        before = runtime.registry.require("hyp-live")
        events = runtime.bus.history(RESEARCH_DECAY_TOPIC, limit=20)
        if events:
            try:
                runtime.bus.publish(
                    topic=RESEARCH_DECAY_TOPIC,
                    producer=MONITOR_AGENT_ID,
                    payload=dict(events[-1].payload),
                )
            except PermissionError:
                pass
            else:
                raise AssertionError("replay must be refused")
        after = runtime.registry.require("hyp-live")
        if after.stage != before.stage or after.weight != before.weight:
            raise AssertionError("replay must not change the book")

        _admit(runtime, "hyp-es", 2, instrument="ES", quantity=2.0, notional=12_000.0)
        _admit(runtime, "hyp-mes", 3, instrument="MES", quantity=2.0, notional=12_000.0)
        if runtime.registry.require("hyp-es").cluster_id != runtime.registry.require("hyp-mes").cluster_id:
            raise AssertionError("ES and MES must share a cluster")
        runtime.rebalance()
        total = sum(item.effective_notional() for item in runtime.registry.signals() if item.instrument in {"ES", "MES"})
        cap = runtime.config.max_cluster_notional_pct * runtime.config.equity
        if total > cap + 1e-6:
            raise AssertionError("cluster cap must bind MES+ES")

        object.__setattr__(runtime, "_snapshot", replace(runtime._snapshot, live_risk_hash="deadbeef"))
        try:
            runtime.observe("hyp-live", 0.8)
        except (ContinuityIntegrityError, ContinuityRefused):
            pass
        else:
            raise AssertionError("observe after Risk Core drift must fail closed")
