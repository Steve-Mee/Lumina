"""Approval Twin shadow promotion evaluation + backend builder."""
from __future__ import annotations

from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.approval_twin_backends import (
    ApprovalTwinBackend,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)
from lumina_core.evolution.approval_twin_patch_bridge import twin_attr
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.logging_utils import (
    correlation_id,
    get_logger,
    record_shadow_twin_alignment_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinShadowEvaluatorMixin:
    def _build_backend(self, *, backend: str | None, ollama_model: str | None) -> tuple[str, ApprovalTwinBackend]:
        cfg = ConfigLoader.section("evolution", "approval_twin", default={})
        cfg = cfg if isinstance(cfg, dict) else {}

        resolved_backend = (
            str(
                backend
                or cfg.get("backend")
                or ConfigLoader.section("ai", "approval_twin_backend", default="")
                or "local"
            )
            .strip()
            .lower()
        )

        if resolved_backend == "ollama":
            model = str(
                ollama_model
                or cfg.get("ollama_model")
                or ConfigLoader.section("ai", "approval_twin_ollama_model", default="")
                or "qwen2.5:3b-instruct"
            ).strip()
            return "ollama", OllamaTwinBackend(model=model)

        return "local", LocalHeuristicBackend()

    def evaluate_shadow_promotion(
        self, *, dna: PolicyDNA, shadow_total_pnl: float, veto_blocked: bool
    ) -> dict[str, Any]:
        dna_hash = str(getattr(dna, "hash", ""))
        with correlation_id(dna_hash):
            base = self.evaluate_dna_promotion(dna)  # already applies _calibrate for confidence
            shadow_positive = float(shadow_total_pnl) > 0.0
            recommendation = bool(base.get("recommendation", False) and shadow_positive and not bool(veto_blocked))
            explanation = (
                f"{base.get('explanation', '')}; shadow_total_pnl={float(shadow_total_pnl):.4f}; "
                f"veto_blocked={bool(veto_blocked)}"
            )
            try:
                logger.info(
                    "twin.evaluate_shadow_promotion",
                    extra={
                        "event_data": {
                            "event": "twin.evaluate_shadow_promotion",
                            "dna_hash": dna_hash,
                            "shadow_total_pnl": float(shadow_total_pnl),
                            "veto_blocked": bool(veto_blocked),
                            "recommendation": recommendation,
                            "risk_flags": list(base.get("risk_flags", [])),
                            "explanation": explanation,
                        }
                    },
                )
                if not recommendation:
                    logger.warning(
                        "twin.shadow_rejection",
                        extra={
                            "event_data": {
                                "event": "twin.shadow_rejection",
                                "dna_hash": dna_hash,
                                "shadow_total_pnl": float(shadow_total_pnl),
                                "veto_blocked": bool(veto_blocked),
                            }
                        },
                    )
            except Exception:
                pass

            confidence = float(base.get("confidence", 0.0) or 0.0)
            risk_flags = list(base.get("risk_flags", []) or [])
            # Perfect Birth KPI: shadow / twin alignment + durable promotion evidence
            try:
                shadow_positive = float(shadow_total_pnl) > 0.0
                ground_truth = bool(shadow_positive and not veto_blocked)
                aligned = (bool(recommendation) and ground_truth) or (
                    not bool(recommendation) and not ground_truth
                )
                twin_attr("record_shadow_twin_alignment_monitoring", record_shadow_twin_alignment_monitoring)(
                    aligned=bool(aligned),
                    shadow_pnl=float(shadow_total_pnl),
                    twin_recommendation=bool(recommendation),
                    confidence=confidence,
                    dna_hash=dna_hash,
                )
                self._publish_shadow_observation(
                    dna_hash=dna_hash,
                    source_topic="evaluate_shadow_promotion",
                    twin_recommendation=bool(recommendation),
                    observed_allowed_or_pass=ground_truth,
                    agreed=bool(aligned),
                    confidence=confidence,
                    risk_flags=risk_flags,
                    explanation=explanation,
                )
                self.observations_total += 1
                if aligned:
                    self.agreements += 1
                else:
                    self.disagreements += 1
                # Durable metrics for TwinModePromotionGate (same path as bus observations)
                constitution_fatal = any(
                    "constitution" in str(f).lower() or "fatal" in str(f).lower()
                    for f in risk_flags
                )
                self._metrics_store.record_comparison(
                    twin_recommendation=bool(recommendation),
                    ground_truth_approve=ground_truth,
                    source="shadow_path",
                    risk_flags=list(risk_flags or []),
                    dna_hash=str(dna_hash or ""),
                    mode=self._mode,
                    constitution_fatal=bool(constitution_fatal),
                    twin_confidence=float(confidence),
                )
            except Exception:
                pass

            decision = {
                **base,
                "recommendation": recommendation,
                "confidence": float(confidence),
                "risk_flags": list(risk_flags or []),
                "shadow_total_pnl": float(shadow_total_pnl),
                "veto_blocked": bool(veto_blocked),
                "explanation": explanation,
            }
            # Authority first; post-hoc notify never blocks shadow judgment.
            return self._finalize_and_publish_decision(
                decision, dna_hash=dna_hash, call="evaluate_shadow_promotion"
            )
