from __future__ import annotations

import logging
from typing import Any, Protocol
from pathlib import Path

from lumina_core.config_loader import ConfigLoader
from lumina_core.agent_orchestration.event_bus import ConstitutionViolation, EventBus
from lumina_core.engine.backtest.reality_gap import RealityGapTracker
from lumina_core.engine.stress_suite_runner import StressSuiteRunner

from .approval_twin_agent import ApprovalTwinAgent
from .dna_registry import PolicyDNA
from .fitness_evaluator import utcnow
from .promotion_gate import PromotionGateDecision, PromotionGateEvidence
from .multi_day_sim_runner import MultiDaySimRunner
from .rollout import EvolutionRolloutFramework
from .shadow_run_storage import load_shadow_runs, save_shadow_runs
from .veto_window import VetoWindow


class PromotionPolicyProtocol(Protocol):
    def run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]: ...

    def mark_shadow_promoted(self, *, dna_hash: str) -> None: ...

    def load_shadow_runs(self) -> dict[str, Any]: ...

    def save_shadow_runs(self, payload: dict[str, Any]) -> None: ...


class _OrchestratorContext(Protocol):
    _guard: Any
    _approval_twin: ApprovalTwinAgent
    _telegram_notifier: Any
    _notification_scheduler: Any
    _veto_registry: Any
    _shadow_state_path: Any
    _promotion_gate: Any


class PromotionPolicy:
    def __init__(
        self,
        owner: _OrchestratorContext,
        logger: logging.Logger | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._owner = owner
        self._logger = logger or logging.getLogger(__name__)
        self._event_bus = event_bus

    @staticmethod
    def _as_float_list(values: Any) -> list[float]:
        if not isinstance(values, list):
            return []
        out: list[float] = []
        for item in values:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                continue
        return out

    def _build_promotion_evidence(
        self,
        *,
        dna: PolicyDNA,
        record: dict[str, Any],
        nightly_report: dict[str, Any],
    ) -> PromotionGateEvidence:
        report = dict(nightly_report or {})
        reality_gap_stats = dict(report.get("reality_gap_stats", {}) or {})
        if not reality_gap_stats:
            gap_tracker = RealityGapTracker(history_path=Path("state/reality_gap_history.jsonl"))
            gap_tracker.load_history()
            reality_gap_stats = gap_tracker.rolling_stats()

        stress_report = dict(report.get("stress_report", {}) or {})
        if not stress_report:
            metrics_realism = dict(report.get("metrics_realism", {}) or {})
            if not metrics_realism:
                metrics_realism = {
                    "pnl_realized": float(report.get("net_pnl", 0.0) or 0.0),
                    "max_drawdown": abs(float(report.get("max_drawdown", 0.0) or 0.0)),
                    "var_breach_count": int(report.get("var_breach_count", 0) or 0),
                }
            stress_report = StressSuiteRunner().build_report(metrics_realism)

        # Shadow / sim promotion evidence — not broker-confirmed economic_pnl.
        shadow_daily_pnl_samples = self._as_float_list(record.get("daily_pnl", []))
        if not shadow_daily_pnl_samples:
            shadow_daily_pnl_samples = [float(record.get("shadow_total_pnl", 0.0) or 0.0)]

        backtest_pnl_samples = self._as_float_list(report.get("backtest_pnl_samples", []))
        if not backtest_pnl_samples:
            baseline = float(report.get("net_pnl", 0.0) or 0.0)
            # Fail-closed behavior remains in PromotionGate (insufficient samples fail).
            backtest_pnl_samples = [baseline] * max(1, len(shadow_daily_pnl_samples))

        cv_combinatorial = dict(report.get("combinatorial_purged_cv", {}) or {})
        cv_walk_forward = dict(report.get("purged_walk_forward", {}) or {})

        return PromotionGateEvidence(
            dna_hash=str(dna.hash),
            cv_combinatorial=cv_combinatorial,
            cv_walk_forward=cv_walk_forward,
            reality_gap_stats=reality_gap_stats,
            stress_report=stress_report,
            live_pnl_samples=shadow_daily_pnl_samples,
            backtest_pnl_samples=backtest_pnl_samples,
            min_sample_trades=int(report.get("min_sample_trades", 30) or 30),
            starting_equity=float(report.get("account_equity", 50_000.0) or 50_000.0),
            backtest_fill_rate=float(report["backtest_fill_rate"])
            if report.get("backtest_fill_rate") is not None
            else None,
            live_fill_rate=float(report["live_fill_rate"]) if report.get("live_fill_rate") is not None else None,
            backtest_slippage=float(report["backtest_slippage"])
            if report.get("backtest_slippage") is not None
            else None,
            live_slippage=float(report["live_slippage"]) if report.get("live_slippage") is not None else None,
        )

    def _publish_promotion_gate_violation(self, *, dna_hash: str, decision: PromotionGateDecision) -> None:
        if self._event_bus is None:
            return
        payload = ConstitutionViolation(
            principle_name="promotion_gate_failed",
            severity="fatal",
            description="REAL promotion blocked by PromotionGate",
            detail=";".join(list(decision.fail_reasons)),
            mode="real",
        ).model_dump(mode="json")
        payload["dna_hash"] = str(dna_hash)
        self._event_bus.publish_validated(
            topic="safety.constitution.violation",
            producer="evolution.promotion_policy",
            payload=payload,
            metadata={"dna_hash": str(dna_hash), "gate": "promotion_gate"},
        )

    def send_shadow_status_telegram(self, message: str) -> None:
        def _send() -> bool:
            return self._owner._telegram_notifier._send_telegram_message(message)

        try:
            self._owner._notification_scheduler.schedule_notification(
                callback=_send,
                description=f"shadow_status:{message[:50]}",
            )
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/promotion_policy.py:159")
            self._logger.warning("[SHADOWTWIN] Telegram notification failed: %s", exc)

    def send_promotion_status_telegram(self, *, dna_hash: str, promoted: bool, reason: str = "") -> None:
        status = "PROMOTED" if promoted else "VETOED"
        message = f"{status}\nDNA: {str(dna_hash)[:12]}"
        if reason:
            message = f"{message}\nReason: {reason}"
        self.send_shadow_status_telegram(message)

    def resolve_shadow_day_bounds(self) -> tuple[int, int]:
        evolution_cfg = ConfigLoader.section("evolution", default={})
        if not isinstance(evolution_cfg, dict):
            return 3, 7
        shadow_cfg = evolution_cfg.get("shadow_validation", {})
        if not isinstance(shadow_cfg, dict):
            return 3, 7
        min_days = max(1, int(shadow_cfg.get("min_days", 3) or 3))
        max_days = max(min_days, int(shadow_cfg.get("max_days", 7) or 7))
        return min_days, max_days

    def veto_window_for_days(self, days: int) -> VetoWindow:
        return VetoWindow(
            veto_registry=self._owner._veto_registry,
            window_seconds=max(1, int(days)) * 24 * 60 * 60,
        )

    def load_shadow_runs(self) -> dict[str, Any]:
        return load_shadow_runs(self._owner._shadow_state_path)

    def save_shadow_runs(self, payload: dict[str, Any]) -> None:
        save_shadow_runs(self._owner._shadow_state_path, payload)

    def mark_shadow_promoted(self, *, dna_hash: str) -> None:
        shadow_runs = self.load_shadow_runs()
        record = dict(shadow_runs.get(dna_hash, {}) or {})
        if not record:
            return
        record["status"] = "promoted"
        record["updated_at"] = utcnow()
        shadow_runs[dna_hash] = record
        self.save_shadow_runs(shadow_runs)

    def run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]:
        if not signed or not generation_ok:
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "guard_not_satisfied", "active_veto_records": []},
                "shadow_status": "guard_blocked",
                "shadow_passed": False,
                "shadow_days_completed": 0,
                "shadow_days_target": 0,
                "shadow_total_pnl": 0.0,
            }

        shadow_runs = self.load_shadow_runs()
        record = dict(shadow_runs.get(dna.hash, {}) or {})
        if not record:
            min_days, max_days = self.resolve_shadow_day_bounds()
            target_days = self._owner._guard.resolve_shadow_days(minimum_days=min_days, maximum_days=max_days)
            record = {
                "dna_hash": dna.hash,
                "lineage_hash": str(dna.lineage_hash),
                "started_at": utcnow(),
                "updated_at": utcnow(),
                "target_days": target_days,
                "status": "pending",
                "winner_fitness": float(winner_fitness),
                "daily_pnl": [],
                "daily_fill_count": [],
                "shadow_total_pnl": 0.0,
            }
            shadow_runs[dna.hash] = record
            self.save_shadow_runs(shadow_runs)
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "shadow_started", "active_veto_records": []},
                "shadow_status": "pending",
                "shadow_passed": False,
                "shadow_days_completed": 0,
                "shadow_days_target": int(target_days),
                "shadow_total_pnl": 0.0,
            }

        status = str(record.get("status", "pending")).strip().lower()
        if status == "promoted":
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "already_promoted", "active_veto_records": []},
                "shadow_status": "promoted",
                "shadow_passed": True,
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }
        if status in {"failed", "vetoed"}:
            vetoed = status == "vetoed"
            return {
                "promote_now": False,
                "veto_blocked": vetoed,
                "veto_check": {
                    "is_blocked": vetoed,
                    "reason": "shadow_failed_or_vetoed",
                    "active_veto_records": [],
                },
                "shadow_status": status,
                "shadow_passed": False,
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }

        target_days = max(1, int(record.get("target_days", 3) or 3))
        daily_pnl = [float(item) for item in list(record.get("daily_pnl", []) or [])]
        daily_fill_count = [int(item) for item in list(record.get("daily_fill_count", []) or [])]

        if len(daily_pnl) < target_days:
            try:
                self._owner._telegram_notifier.poll_for_replies()
            except Exception as exc:
                logging.exception("Unhandled broad exception fallback in lumina_core/evolution/promotion_policy.py:290")
                self._logger.warning("[SHADOWTWIN] Telegram poll failed: %s", exc)
            if self._owner._telegram_notifier.is_vetoed_or_expired(dna.hash):
                record["status"] = "vetoed"
                record["updated_at"] = utcnow()
                shadow_runs[dna.hash] = record
                self.save_shadow_runs(shadow_runs)
                return {
                    "promote_now": False,
                    "veto_blocked": True,
                    "veto_check": {"is_blocked": True, "reason": "telegram_veto", "active_veto_records": []},
                    "shadow_status": "vetoed",
                    "shadow_passed": False,
                    "shadow_days_completed": len(daily_pnl),
                    "shadow_days_target": target_days,
                    "shadow_total_pnl": float(sum(daily_pnl)),
                }

            shadow_results = shadow_runner.evaluate_variants(
                [dna],
                days=1,
                nightly_report=nightly_report,
                **EvolutionRolloutFramework.shadow_runtime_flags(),
            )
            latest = shadow_results[0] if shadow_results else None
            day_pnl = float(latest.avg_pnl) if latest is not None else 0.0
            fill_count = len(list(latest.hypothetical_fills or [])) if latest is not None else 0
            daily_pnl.append(day_pnl)
            daily_fill_count.append(fill_count)
            record["daily_pnl"] = daily_pnl
            record["daily_fill_count"] = daily_fill_count
            record["shadow_total_pnl"] = float(sum(daily_pnl))
            record["updated_at"] = utcnow()
            shadow_runs[dna.hash] = record
            self.save_shadow_runs(shadow_runs)

        shadow_total_pnl = float(sum(daily_pnl))
        veto_check = self.veto_window_for_days(target_days).check_with_details(dna_id=dna.hash)
        veto_blocked = bool(veto_check.get("is_blocked", False))
        if len(daily_pnl) < target_days:
            return {
                "promote_now": False,
                "veto_blocked": veto_blocked,
                "veto_check": veto_check,
                "shadow_status": "pending",
                "shadow_passed": False,
                "shadow_days_completed": len(daily_pnl),
                "shadow_days_target": target_days,
                "shadow_total_pnl": shadow_total_pnl,
            }

        shadow_twin = self._owner._approval_twin.evaluate_shadow_promotion(
            dna=dna,
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
        )
        risk_flags = list(shadow_twin.get("risk_flags", []) or [])
        shadow_passed = self._owner._guard.shadow_validation_passed(
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
            risk_flags=risk_flags,
        )
        gate_decision_payload: dict[str, Any] | None = None
        if shadow_passed:
            try:
                evidence = self._build_promotion_evidence(
                    dna=dna,
                    record=record,
                    nightly_report=nightly_report,
                )
                gate_decision = self._owner._promotion_gate.evaluate(dna_hash=dna.hash, evidence=evidence)
                gate_decision_payload = gate_decision.model_dump(mode="json")
                if not bool(gate_decision.promoted):
                    shadow_passed = False
                    self._publish_promotion_gate_violation(dna_hash=dna.hash, decision=gate_decision)
            except Exception as exc:
                logging.exception("Unhandled broad exception fallback in lumina_core/evolution/promotion_policy.py:365")
                self._logger.error("PromotionGate evaluate failed (fail-closed) dna=%s err=%s", dna.hash[:12], exc)
                shadow_passed = False
                fallback_decision = PromotionGateDecision(
                    dna_hash=str(dna.hash),
                    promoted=False,
                    criteria=[],
                    timestamp=utcnow(),
                    config_snapshot={},
                    fail_reasons=("evidence_unavailable",),
                )
                self._publish_promotion_gate_violation(dna_hash=dna.hash, decision=fallback_decision)
                gate_decision_payload = fallback_decision.model_dump(mode="json")

        record["status"] = "passed" if shadow_passed else ("vetoed" if veto_blocked else "failed")
        record["shadow_total_pnl"] = shadow_total_pnl
        record["updated_at"] = utcnow()
        record["shadow_decision"] = {
            "recommendation": bool(shadow_twin.get("recommendation", False)),
            "confidence": float(shadow_twin.get("confidence", 0.0) or 0.0),
            "risk_flags": risk_flags,
            "explanation": str(shadow_twin.get("explanation", "")),
        }
        if gate_decision_payload is not None:
            record["promotion_gate"] = gate_decision_payload
        shadow_runs[dna.hash] = record
        self.save_shadow_runs(shadow_runs)
        return {
            "promote_now": shadow_passed,
            "veto_blocked": veto_blocked,
            "veto_check": veto_check,
            "shadow_status": str(record.get("status", "pending")),
            "shadow_passed": shadow_passed,
            "shadow_days_completed": len(daily_pnl),
            "shadow_days_target": target_days,
            "shadow_total_pnl": shadow_total_pnl,
            "promotion_gate": gate_decision_payload or {},
        }
