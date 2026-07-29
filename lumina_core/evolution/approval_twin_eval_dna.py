"""Approval Twin DNA promotion evaluation."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.logging_utils import (
    classify_twin_decision_outcome,
    correlation_id,
    get_logger,
    log_twin_decision,
    record_twin_decision_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinDnaEvaluatorMixin:
    def evaluate_dna_promotion(self, dna: PolicyDNA) -> dict[str, Any]:
        dna_hash = str(getattr(dna, "hash", ""))
        with correlation_id(dna_hash):
            features = self._features_from_dna(dna)
            local_score = self._score(features)
            backend_score, backend_explanation = self._backend.score(
                dna=dna,
                local_score=local_score,
                threshold=self._state.threshold,
            )
            raw_score = float(backend_score if backend_score is not None else local_score)
            raw_score = max(0.0, min(1.0, raw_score))
            # Calibrated confidence (used for recommendation + "high conf" autonomy decisions)
            score = self._calibrate(raw_score)
            risk_flags = self._risk_flags(dna)
            recommendation = bool(score >= self._state.threshold and not risk_flags)
            shadow_suffix = ""

            # === Constitution hard veto (fail-closed) — twin can NEVER recommend unconstitutional DNA ===
            # This is the structural guarantee that the ApprovalTwin (judgment layer) cannot bypass
            # TradingConstitution / ConstitutionalGuard / sandbox / aperture. Even if the heuristic or
            # Ollama backend is tricked by crafted content (safety words, high fitness, low mut rate),
            # any FATAL principle violation forces recommendation=False + explicit risk flag.
            # Proxy / birth-autonomy synthetic DNA (non-trading shape) is handled gracefully: we only
            # enforce when the content parses as a plausible trading DNA (presence of hyperparams or
            # standard keys). Any exception during the check is treated as fatal (fail-closed).
            # Must run before risk shadow incorporation so constitution takes precedence.
            try:
                raw_content = getattr(dna, "content", {}) or {}
                if isinstance(raw_content, str):
                    import json as _json
                    try:
                        content_for_audit = _json.loads(raw_content)
                    except Exception:
                        content_for_audit = {}
                else:
                    content_for_audit = raw_content

                # Heuristic: only apply strict trading constitution when it looks like real DNA
                # (not pure birth proxy metadata). If only the "structured" principle would fire,
                # we treat as non-trading and skip the veto for autonomy meta-decisions.
                looks_like_trading_dna = bool(
                    isinstance(content_for_audit, dict)
                    and (
                        "hyperparam_suggestion" in content_for_audit
                        or "mutation_depth" in content_for_audit
                        or any(k in content_for_audit for k in ("max_risk_percent", "kelly_fraction", "drawdown_kill_percent", "risk", "signal", "bypass", "disable_risk", "disable_circuit", "approval_required"))
                        or any(str(k).startswith(("bypass_", "disable_")) for k in content_for_audit.keys())
                        or (isinstance(content_for_audit.get("content"), str) and len(str(content_for_audit.get("content"))) > 10)
                    )
                )

                if looks_like_trading_dna:
                    from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION
                    # stringify for the audit API (accepts raw JSON string or will parse)
                    audit_input = _json.dumps(content_for_audit, sort_keys=True) if isinstance(content_for_audit, dict) else str(content_for_audit)
                    violations = TRADING_CONSTITUTION.audit(audit_input, mode="sim", raise_on_fatal=False)
                    fatals = [v for v in violations if getattr(v, "severity", "") == "fatal"]
                    if fatals:
                        recommendation = False
                        for fv in fatals:
                            flag = f"constitution_{getattr(fv, 'principle_name', 'fatal')}"
                            if flag not in risk_flags:
                                risk_flags.append(flag)
                        # ensure the generic marker too
                        if "constitution_fatal_violation" not in risk_flags:
                            risk_flags.append("constitution_fatal_violation")
            except Exception:
                # Fail-closed: any error in the twin's constitution check blocks recommendation.
                # This prevents a tricked / broken twin from ever allowing bad DNA through its output.
                recommendation = False
                if "twin_constitution_check_error" not in risk_flags:
                    risk_flags.append("twin_constitution_check_error")
            # ================================================================================

            # === Phase 2 Deliverable 5 (Aperture Hardening) — Proactive risk shadow validation ===
            # For any DNA evaluation where an engine is available, we proactively run
            # the risk logic through the isolated shadow aperture. This is the first
            # live enforcement point where evolution proposals are forced through
            # the shadow aperture before promotion decisions (using bridge + auto-record).
            #
            # We attempt to extract realistic risk parameters from the DNA content
            # so the shadow experiment is meaningful rather than using only defaults.
            if self._engine is not None:
                try:
                    from pathlib import Path

                    # Best-effort extraction of risk experiment parameters from DNA
                    content = getattr(dna, "content", {}) or {}
                    if isinstance(content, str):
                        import json
                        try:
                            content = json.loads(content)
                        except Exception:
                            content = {}

                    proposal = {
                        "experiment_id": f"risk-shadow-{dna_hash[:12]}",
                        "dna_hash": dna_hash,
                        "signal": content.get("signal") or content.get("action") or "BUY",
                        "confluence_score": float(content.get("confluence_score", content.get("confluence", 0.65))),
                        "proposed_risk": float(content.get("proposed_risk", content.get("risk", 150.0))),
                    }

                    from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow

                    shadow_result = validate_risk_proposal_in_shadow(
                        proposal=proposal,
                        engine=self._engine,
                        storage_path=Path("state/risk_shadow_evolution.jsonl"),
                        auto_record_promotion=True,
                    )

                    # Incorporate shadow outcome into the twin decision
                    # NOTE: this path (and all twin risk proposals) is protected by the permanent
                    # aperture regression detector (aperture_guard). Twin cannot create bypasses.
                    shadow_rec = shadow_result.recommendation or {}
                    if shadow_rec.get("suggested_stage") in ("human_approval", "reject"):
                        recommendation = False
                        risk_flags.append("risk_shadow_blocked")
                    shadow_suffix = f" | risk_shadow={shadow_rec.get('suggested_stage', 'unknown')}"
                except Exception:
                    # Shadow validation is best-effort; never break the twin gate
                    pass
            # ================================================================================
            explanation = (
                f"Twin score={score:.2%}, threshold={self._state.threshold:.0%}, backend={self._backend_name}, "
                f"fitness={float(dna.fitness_score):.4f}, mutation_rate={float(dna.mutation_rate):.2f}, "
                f"source={backend_explanation}{shadow_suffix}"
            )
            try:
                logger.info(
                    "twin.evaluate_promotion",
                    extra={
                        "event_data": {
                            "event": "twin.evaluate_promotion",
                            "dna_hash": dna_hash,
                            "features": features,
                            "local_score": local_score,
                            "backend_score": backend_score,
                            "final_score": score,
                            "threshold": self._state.threshold,
                            "risk_flags": risk_flags,
                            "recommendation": recommendation,
                            "explanation": explanation,
                        }
                    },
                )
                log_twin_decision(logger, dna_hash, score, recommendation, risk_flags, explanation)
                outcome = classify_twin_decision_outcome(
                    recommendation=recommendation, score=score, risk_flags=risk_flags
                )
                twin_attr("record_twin_decision_monitoring", record_twin_decision_monitoring)(
                    dna_hash=dna_hash,
                    score=score,
                    recommendation=recommendation,
                    risk_flags=risk_flags,
                    explanation=explanation,
                    mode=self._mode,
                    outcome=outcome,
                )
                if not recommendation:
                    logger.warning(
                        "twin.evaluate_rejection",
                        extra={
                            "event_data": {
                                "event": "twin.evaluate_rejection",
                                "dna_hash": dna_hash,
                                "final_score": score,
                                "threshold": self._state.threshold,
                                "risk_flags": risk_flags,
                            }
                        },
                    )
            except Exception:
                pass

            # Publish typed event to central bus (best effort; after logs)
            self._publish_decision(
                dna_hash=dna_hash,
                recommendation=recommendation,
                confidence=score,
                risk_flags=risk_flags,
                explanation=explanation,
                call="evaluate_dna_promotion",
            )

            decision = {
                "recommendation": recommendation,
                "confidence": round(score, 6),
                "explanation": explanation,
                "risk_flags": risk_flags,
            }
            # Mode authority: shadow/assisted cannot sole-auto-approve (fail-closed)
            return self.apply_mode_authority(decision)
