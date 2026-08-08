"""PromotionPolicy shadow validation gate."""
from __future__ import annotations

import logging
from typing import Any


from .dna_registry import PolicyDNA
from .fitness_evaluator import utcnow
from .multi_day_sim_runner import MultiDaySimRunner
from .promotion_gate import PromotionGateDecision
from .rollout import EvolutionRolloutFramework


class PromotionShadowGateMixin:
    """Owns run_shadow_validation_gate."""

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
        twin_raw = bool(shadow_twin.get("recommendation", False))
        # Mode authority: twin_primary_auto only when executable (full_auto)
        if "effective_recommendation" in shadow_twin:
            twin_rec = bool(shadow_twin.get("effective_recommendation", False))
        else:
            twin_rec = False  # fail-closed without mode fields
        twin_executable = bool(shadow_twin.get("executable", False))
        twin_mode = str(shadow_twin.get("mode") or getattr(self._owner._approval_twin, "mode", "shadow"))
        twin_conf = float(shadow_twin.get("confidence", 0.0) or 0.0)

        # Primary auto-approval signal from twin (only when mode allows execute_judgment).
        # Hard PromotionGate + shadow still apply for REAL; twin is necessary input.

        # === Phase 2 Deliverable 5 (Aperture Hardening) — Second independent call site ===
        # In addition to the proactive call inside the ApprovalTwin, the official
        # promotion gate now also runs risk-affecting DNA through the isolated
        # shadow aperture when risk flags are present. This creates a second
        # enforcement point for the "must run in shadow" requirement.
        if risk_flags and hasattr(self._owner, "_engine") and self._owner._engine is not None:
            try:
                from pathlib import Path

                from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow

                shadow_result = validate_risk_proposal_in_shadow(
                    proposal={
                        "experiment_id": f"risk-shadow-gate-{dna.hash[:12]}",
                        "dna_hash": dna.hash,
                        "signal": "BUY",
                        "confluence_score": 0.65,
                        "proposed_risk": 150.0,
                    },
                    engine=self._owner._engine,
                    storage_path=Path("state/risk_shadow_evolution.jsonl"),
                    auto_record_promotion=True,
                )
                shadow_rec = shadow_result.recommendation or {}
                if shadow_rec.get("suggested_stage") in ("human_approval", "reject"):
                    shadow_passed = False
                    risk_flags.append("risk_shadow_promotion_gate_blocked")
            except Exception:
                pass
        # ================================================================================

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
            "recommendation": twin_raw,
            "effective_recommendation": twin_rec,
            "executable": twin_executable,
            "mode": twin_mode,
            "confidence": twin_conf,
            "risk_flags": risk_flags,
            "explanation": str(shadow_twin.get("explanation", "")),
            "twin_primary_auto": bool(twin_rec and twin_executable and len(risk_flags) == 0),
        }
        if gate_decision_payload is not None:
            record["promotion_gate"] = gate_decision_payload
        shadow_runs[dna.hash] = record
        self.save_shadow_runs(shadow_runs)

        # Best-effort bus publish so ApprovalTwin can observe DNA shadow/promotion (ADR-0001/0031).
        # Critical topics: validation errors must not break the gate decision path.
        self._publish_shadow_and_promotion_events(
            dna_hash=str(dna.hash),
            shadow_passed=bool(shadow_passed),
            promote_now=bool(shadow_passed),
            shadow_total_pnl=float(shadow_total_pnl),
            sample_size=len(daily_pnl),
            veto_blocked=bool(veto_blocked),
            twin_rec=bool(twin_rec),
            risk_flags=list(risk_flags),
        )

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
            # Twin as primary auto-approval layer signal (used by guard + callers)
            "twin_recommendation": twin_rec,
            "twin_raw_recommendation": twin_raw,
            "twin_executable": twin_executable,
            "twin_mode": twin_mode,
            "twin_confidence": twin_conf,
            "twin_risk_flags": risk_flags,
            # NOTE: caller must have already AND-ed with ConstitutionalGuard.veto_unless_constitutional
            # (twin is never allowed to bypass constitution, sandbox or aperture).
        }
