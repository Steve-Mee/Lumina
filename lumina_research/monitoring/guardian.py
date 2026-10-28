"""Daily and weekly Research Charter scans. Violations propose suspension only."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import (
    GUARDIAN_AGENT_ID,
    GuardianCadence,
    GuardianFinding,
    GuardianSeverity,
    RESEARCH_GUARDIAN_TOPIC,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.objects import as_object_dict
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.evolution.integrity import IntegrityError, IntegritySnapshot, assert_intact
from lumina_research.monitoring.config import ContinuityConfig
from lumina_research.monitoring.registry import LiveSignalRegistry
from lumina_research.monitoring.report import GuardianReport, log_decision
from lumina_research.monitoring.seal import accept_mac, canonical_guardian
from lumina_research.monitoring.types import MIN_LIVE_OOS_VALUES, ContinuityRefused, LiveSignal
from lumina_research.validation.cost_model import COST_MODEL_ID
from lumina_research.validation.thresholds import FLOOR_DSR_PROBABILITY_MIN
from lumina_research.validation.trial_registry import TrialRecord


class GuardianAgent(Frozen):
    """Fail-closed charter scanner. Missing evidence is a violation."""

    _bus: EventBus
    _registry: LiveSignalRegistry
    _authority: ProvenanceAuthority
    _config: ContinuityConfig
    _log_path: Path
    _blackboard: AgentBlackboard | None
    _evolution_log_dir: Path | None
    _findings: list[GuardianFinding]
    _seq: list[int]
    _seen: set[str]

    def __init_subclass__(cls) -> None:
        raise TypeError("GuardianAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        registry: LiveSignalRegistry,
        authority: ProvenanceAuthority,
        config: ContinuityConfig,
        experiment_log_path: Path,
        blackboard: AgentBlackboard | None = None,
        evolution_log_dir: Path | None = None,
    ) -> None:
        self._bus = bus
        self._registry = registry
        self._authority = authority
        self._config = config
        self._log_path = experiment_log_path
        self._blackboard = blackboard
        self._evolution_log_dir = evolution_log_dir
        self._findings = []
        self._seq = [0]
        self._seen = set()
        self._freeze()
        bus.register_topic_guard(RESEARCH_GUARDIAN_TOPIC, self._guard)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_GUARDIAN_TOPIC, self._guard_bb)

    def findings(self) -> tuple[GuardianFinding, ...]:
        return tuple(self._findings)

    def set_risk_limits(self) -> None:
        raise ContinuityRefused("monitoring cannot mutate Risk Core")

    def scan(
        self,
        *,
        cadence: GuardianCadence,
        baseline: IntegritySnapshot,
        trials: Sequence[TrialRecord],
        decisions: Sequence[Mapping[str, object]] = (),
        live: IntegritySnapshot | None = None,
    ) -> GuardianReport:
        try:
            return self._scan_body(
                cadence=cadence,
                baseline=baseline,
                trials=trials,
                decisions=decisions,
                live=live,
            )
        except ContinuityRefused:
            raise
        except Exception as exc:
            raise ContinuityRefused(f"guardian failed closed: {exc}") from exc

    def _scan_body(
        self,
        *,
        cadence: GuardianCadence,
        baseline: IntegritySnapshot,
        trials: Sequence[TrialRecord],
        decisions: Sequence[Mapping[str, object]],
        live: IntegritySnapshot | None,
    ) -> GuardianReport:
        signals = self._registry.signals()
        emitted: list[GuardianFinding] = []
        if live is None:
            integrity_ok, integrity_detail = _integrity(baseline)
        else:
            integrity_ok, integrity_detail = (
                live.live_risk_hash == baseline.live_risk_hash
                and live.research_risk_hash == baseline.research_risk_hash,
                "risk_core_hash",
            )
            if integrity_ok:
                try:
                    assert_intact(baseline)
                except IntegrityError as exc:
                    integrity_ok, integrity_detail = False, str(exc)
        emitted.append(
            self._finding(
                cadence=cadence,
                check_id="risk_core_untouched",
                signal_id="*",
                passed=integrity_ok,
                severity="ok" if integrity_ok else "violation",
                suspend_proposed=False,
                metric="risk_core_hash",
                observed="intact" if integrity_ok else integrity_detail,
                required="unchanged live and research Risk Core",
            )
        )
        if not integrity_ok:
            for signal in signals:
                if signal.stage == "retired":
                    continue
                emitted.append(
                    self._finding(
                        cadence=cadence,
                        check_id="risk_core_untouched",
                        signal_id=signal.signal_id,
                        passed=False,
                        severity="violation",
                        suspend_proposed=True,
                        metric="risk_core_hash",
                        observed=integrity_detail,
                        required="unchanged live and research Risk Core",
                    )
                )
        trial_ids = {item.trial_id for item in trials}
        live_ids = {item.signal_id for item in signals}
        for signal in signals:
            emitted.extend(self._signal_checks(cadence, signal, trial_ids))
        for raw in decisions:
            emitted.append(self._decision_check(cadence, raw, live_ids))
        n_ok = sum(1 for item in emitted if item.severity == "ok")
        n_warn = sum(1 for item in emitted if item.severity == "warn")
        n_viol = sum(1 for item in emitted if item.severity == "violation")
        suspends = tuple(
            dict.fromkeys(item.signal_id for item in emitted if item.suspend_proposed and item.signal_id != "*")
        )
        return GuardianReport(
            cadence=cadence,
            n_signals=len(signals),
            n_checks=len(emitted),
            n_ok=n_ok,
            n_warn=n_warn,
            n_violations=n_viol,
            suspend_proposals=suspends,
            finding_ids=tuple(item.finding_id for item in emitted),
            passed=n_viol == 0,
        )

    def _signal_checks(
        self,
        cadence: GuardianCadence,
        signal: LiveSignal,
        trial_ids: set[int],
    ) -> list[GuardianFinding]:
        windows_ok = signal.n_oos_windows >= self._config.min_oos_windows
        thin_ok = len(signal.oos_values) >= MIN_LIVE_OOS_VALUES
        purge_ok = signal.purge_applied and signal.embargo_applied
        dsr_ok = signal.dsr_probability >= FLOOR_DSR_PROBABILITY_MIN
        pbo_hard = signal.pbo > self._config.pbo_reject_min
        pbo_warn = signal.pbo > self._config.pbo_promote_max
        cost_ok = signal.cost_applied and signal.cost_model_id == COST_MODEL_ID
        regime_ok = signal.regimes_complete
        trial_ok = signal.trial_id in trial_ids
        sealed = self._registry.verify(signal)
        pbo_severity: GuardianSeverity = "violation" if pbo_hard else ("warn" if pbo_warn else "ok")
        rows: list[tuple[str, bool, GuardianSeverity, bool, str, str, str]] = [
            ("wf_oos_windows", windows_ok, "violation" if not windows_ok else "ok", not windows_ok, "n_oos_windows", str(signal.n_oos_windows), f">={self._config.min_oos_windows}"),
            ("oos_distribution_size", thin_ok, "violation" if not thin_ok else "ok", not thin_ok, "oos_values", str(len(signal.oos_values)), f">={MIN_LIVE_OOS_VALUES}"),
            ("cpcv_purge_embargo", purge_ok, "violation" if not purge_ok else "ok", not purge_ok, "purge_embargo", f"{signal.purge_applied}/{signal.embargo_applied}", "true/true"),
            ("dsr_present", dsr_ok, "violation" if not dsr_ok else "ok", not dsr_ok, "dsr_probability", str(signal.dsr_probability), f">={FLOOR_DSR_PROBABILITY_MIN}"),
            (
                "pbo_band",
                not pbo_hard,
                pbo_severity,
                pbo_hard,
                "pbo",
                str(signal.pbo),
                f"promote<={self._config.pbo_promote_max} reject>{self._config.pbo_reject_min}",
            ),
            ("costs", cost_ok, "violation" if not cost_ok else "ok", not cost_ok, "cost_model", signal.cost_model_id, COST_MODEL_ID),
            ("regimes", regime_ok, "violation" if not regime_ok else "ok", not regime_ok, "regimes_complete", str(signal.regimes_complete), "true"),
            ("trial_logged", trial_ok, "violation" if not trial_ok else "ok", not trial_ok, "trial_id", str(signal.trial_id), "present in TrialRegistry"),
            ("admission_mac", sealed, "violation" if not sealed else "ok", not sealed, "admission_mac", "valid" if sealed else "tampered", "HMAC admission+state seal"),
            ("promotion_via_gate", sealed, "violation" if not sealed else "ok", not sealed, "admission", "sealed" if sealed else "unsealed", "PromotionCandidate+ValidationResult"),
        ]
        out: list[GuardianFinding] = []
        for check_id, passed, severity, suspend, metric, observed, required in rows:
            out.append(
                self._finding(
                    cadence=cadence,
                    check_id=check_id,
                    signal_id=signal.signal_id,
                    passed=passed,
                    severity=severity,
                    suspend_proposed=suspend and signal.stage != "retired",
                    metric=metric,
                    observed=observed,
                    required=required,
                )
            )
        return out

    def _decision_check(
        self,
        cadence: GuardianCadence,
        raw: Mapping[str, object],
        live_ids: set[str],
    ) -> GuardianFinding:
        payload = as_object_dict(raw) or dict(raw)
        hypothesis = str(payload.get("hypothesis_id", "unknown"))
        gated = payload.get("gated")
        if payload.get("kind") == "ungated_promotion" or gated is False or gated is not True:
            via_gate = False
        else:
            via_gate = True
        suspend = (not via_gate) and hypothesis in live_ids
        return self._finding(
            cadence=cadence,
            check_id="promotion_via_gate",
            signal_id=hypothesis,
            passed=via_gate,
            severity="ok" if via_gate else "violation",
            suspend_proposed=suspend,
            metric="gated",
            observed=str(gated),
            required="true",
        )

    def _finding(
        self,
        *,
        cadence: GuardianCadence,
        check_id: str,
        signal_id: str,
        passed: bool,
        severity: GuardianSeverity,
        suspend_proposed: bool,
        metric: str,
        observed: str,
        required: str,
    ) -> GuardianFinding:
        self._seq[0] += 1
        unsigned: dict[str, object] = {
            "schema_version": "research.guardian.finding.v1",
            "finding_id": f"g-{self._seq[0]}-{check_id}",
            "cadence": cadence,
            "check_id": check_id,
            "signal_id": signal_id,
            "agent_id": GUARDIAN_AGENT_ID,
            "passed": passed,
            "severity": severity,
            "suspend_proposed": suspend_proposed,
            "evidence": {"metric": metric, "observed": observed, "required": required},
        }
        mac = self._authority.mac(canonical_guardian(unsigned))
        finding = GuardianFinding.model_validate({**unsigned, "provenance_mac": mac})
        dumped = dump_json(finding)
        self._bus.publish(topic=RESEARCH_GUARDIAN_TOPIC, producer=GUARDIAN_AGENT_ID, payload=dict(dumped))
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_GUARDIAN_TOPIC,
                producer=GUARDIAN_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0 if passed else 0.0,
            )
        self._findings.append(finding)
        log_decision(
            path=self._log_path,
            agent_id=GUARDIAN_AGENT_ID,
            event="guardian",
            signal_id=signal_id,
            metrics=dumped,
            evolution_log_dir=self._evolution_log_dir,
            reject_reason=None if passed else check_id,
            failed_checks=() if passed else (check_id,),
        )
        return finding

    def _guard(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=True)

    def _guard_bb(self, producer: str, payload: dict[str, object]) -> bool:
        return self._check(producer, payload, consume=False)

    def _check(self, producer: str, payload: dict[str, object], *, consume: bool) -> bool:
        if producer.strip() != GUARDIAN_AGENT_ID:
            return False
        try:
            GuardianFinding.model_validate(payload)
        except Exception:
            return False
        return accept_mac(
            self._authority,
            canonical_guardian(payload),
            payload.get("provenance_mac"),
            self._seen if consume else None,
        )


def _integrity(baseline: IntegritySnapshot) -> tuple[bool, str]:
    try:
        assert_intact(baseline)
    except IntegrityError as exc:
        return False, str(exc)
    return True, "intact"
