"""Compact fail-closed battery used to kill monitoring mutants. No pytest."""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.monitoring.capacity import CapacityController
from lumina_research.monitoring.config import ContinuityConfigError, config_from_mapping, load_default_config
from lumina_research.monitoring.guardian import GuardianAgent
from lumina_research.monitoring.loop import ContinuityRuntime
from lumina_research.monitoring.monitor import LivePerformanceMonitor
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.sizing import ContinuitySizer
from lumina_research.monitoring.statistics import assess_decay
from lumina_research.monitoring.synthetic import DEFAULT_OOS, seal_promotion_pair
from lumina_research.monitoring.types import ContinuityRefused
from lumina_research.risk_core.config import load_default_config as load_risk_config
from lumina_research.risk_core.engine import RiskCore


def run() -> None:
    cfg = load_default_config()
    raw = asdict(cfg)
    raw["z_deweight"] = -100.0
    raw["z_suspend"] = -100.0
    raw["z_retire"] = -100.0
    try:
        config_from_mapping(raw)
    except ContinuityConfigError:
        pass
    else:
        raise AssertionError("weak z config must be refused")
    bloated = asdict(cfg)
    bloated["equity"] = 1_000_000_000.0
    try:
        config_from_mapping(bloated)
    except ContinuityConfigError:
        pass
    else:
        raise AssertionError("inflated equity must be refused")

    quiet = assess_decay(tuple(0.8 for _ in range(30)), DEFAULT_OOS, cfg)
    if quiet.ready is not True:
        raise AssertionError("healthy window must be ready")
    loud = assess_decay(tuple(-1.0 for _ in range(30)), DEFAULT_OOS, cfg)
    if loud.severity < 1:
        raise AssertionError("obvious decay must be detected")

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        authority = ProvenanceAuthority()
        registry = LiveSignalRegistry(authority=authority, config=cfg)
        try:
            registry.increase_weight("x", 2.0)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("weight increase must refuse")
        try:
            registry.restore("x")
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("restore must refuse")

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
        try:
            registry.admit(candidate, validation)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("short OOS must be refused")

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
        if signal.weight != 1.0 or not registry.verify(signal):
            raise AssertionError("admit must seal an active signal")
        try:
            registry.insert(signal)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("direct insert must refuse")
        lowered = registry.apply_stage("hyp-ok", "deweighted")
        if lowered.weight >= signal.weight:
            raise AssertionError("deweight must reduce weight")
        try:
            registry.apply_capacity_scale("hyp-ok", 1.5)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("illegal capacity scale must refuse")
        retired = registry.apply_stage("hyp-ok", "retired")
        if retired.weight != 0.0:
            raise AssertionError("retire must zero weight")

        bus = EventBus()
        log = root / "exp.jsonl"
        monitor = LivePerformanceMonitor(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        try:
            monitor.observe("hyp-ok", float("nan"))
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("NaN metric must be refused")
        try:
            monitor.observe("hyp-ok", math.inf)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("inf metric must be refused")

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
        try:
            sizer.propose("hyp-sz", quantity=9.0, price=100.0, at=datetime.now(timezone.utc))
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("oversize quantity must be refused")

        capacity = CapacityController(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        try:
            capacity.scale_up("hyp-sz", 1.0)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("capacity scale-up must refuse")

        guardian = GuardianAgent(
            bus=bus,
            registry=registry,
            authority=authority,
            config=cfg,
            experiment_log_path=log,
        )
        try:
            guardian.set_risk_limits()
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("guardian must not mutate Risk Core")

        runtime = ContinuityRuntime(audit_path=root / "audit.jsonl", experiment_log_path=log)
        try:
            runtime.insert_direct(signal)
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("runtime insert_direct must refuse")
        try:
            runtime.mutate_thresholds()
        except ContinuityRefused:
            pass
        else:
            raise AssertionError("threshold mutation must refuse")


if __name__ == "__main__":
    run()
