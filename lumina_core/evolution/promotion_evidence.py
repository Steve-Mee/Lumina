"""Promotion evidence build + event publish mixin."""
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

# === Phase 2 Deliverable 5 (Aperture Hardening) — Integration Hook ===
# When a DNA/proposal change touches risk logic (policy, limits, gates, sizing, etc.),
# evolution code should validate it in shadow first using the official bridge.
#
# Ergonomic one-call pattern (recommended for most callers):
#
#   from lumina_core.evolution.risk_shadow_bridge import run_risk_shadow_experiment_for_proposal
#   result = run_risk_shadow_experiment_for_proposal(
#       proposal={"experiment_id": ..., "dna_hash": dna.hash, "signal": ..., ...},
#       engine=engine,
#       storage_path=some_registry_path,
#       auto_record_promotion=True,   # <-- new convenience: run + commit promotion decision
#   )
#
# If human review is required, the request will be visible to the shadow_review CLI.
#
# This is the concrete path toward the original requirement:
# "every evolution experiment that touches risk logic must run in a shadow aperture mode".
# ================================================================================


from lumina_core.evolution.promotion_shadow_gate import PromotionShadowGateMixin

class PromotionEvidenceMixin:
    """_build_promotion_evidence + _publish_shadow_and_promotion_events."""

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
    def _publish_shadow_and_promotion_events(
        self,
        *,
        dna_hash: str,
        shadow_passed: bool,
        promote_now: bool,
        shadow_total_pnl: float,
        sample_size: int,
        veto_blocked: bool,
        twin_rec: bool,
        risk_flags: list[str],
    ) -> None:
        """Publish typed shadow/promotion bus events for Twin observe (fail-soft)."""
        if self._event_bus is None:
            return
        try:
            from lumina_core.agent_orchestration.schemas import (
                EvolutionPromotionDecision,
                ShadowResult,
            )

            verdict = "pass" if shadow_passed else ("fail" if not veto_blocked else "fail")
            if not shadow_passed and sample_size <= 0:
                verdict = "pending"
            shadow_payload = ShadowResult(
                verdict=verdict,  # type: ignore[arg-type]
                dna_hash=str(dna_hash),
                sample_size=int(max(0, sample_size)),
                pnl=float(shadow_total_pnl),
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.shadow.verdict",
                producer="evolution.promotion_policy",
                payload=shadow_payload,
                metadata={"dna_hash": str(dna_hash), "veto_blocked": bool(veto_blocked)},
            )

            reason_parts = []
            if not shadow_passed:
                reason_parts.append("shadow_failed" if not veto_blocked else "veto_blocked")
            if risk_flags:
                reason_parts.append("risk_flags:" + ",".join(str(x) for x in risk_flags[:6]))
            if not twin_rec:
                reason_parts.append("twin_reject")
            reason = ";".join(reason_parts) if reason_parts else "shadow_and_twin_ok"
            promo_payload = EvolutionPromotionDecision(
                dna_hash=str(dna_hash),
                allowed=bool(promote_now),
                reason=reason or "promotion_evaluated",
                stage="shadow",
                mode="REAL",
                evidence_ref=None,
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.promotion.decision",
                producer="evolution.promotion_policy",
                payload=promo_payload,
                metadata={"dna_hash": str(dna_hash)},
            )
        except Exception:
            # Observability only — never fail the promotion gate path.
            self._logger.debug("promotion_policy.bus_publish_shadow_promo_failed", exc_info=True)
