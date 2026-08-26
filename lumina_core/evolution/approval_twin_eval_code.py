"""Approval Twin code-proposal evaluation."""
from __future__ import annotations

import json
from typing import Any

from lumina_core.logging_utils import correlation_id, get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinCodeEvaluatorMixin:
    def evaluate_code_proposal(self, proposal: Any) -> dict[str, Any]:
        """Judge a trading-code evolution proposal (ADR-0033).

        Twin provides operator-aligned *judgment* only. Never bypasses
        CodeEvolutionConstitution, ConstitutionalGuard, or SandboxedCodeExecutor.
        Uses proposal_id as correlation id in twin decision events.
        """
        proposal_id = str(getattr(proposal, "proposal_id", "") or "unknown")
        with correlation_id(proposal_id):
            operator = str(
                getattr(getattr(proposal, "operator", None), "value", None)
                or getattr(proposal, "operator", "")
                or ""
            )
            target = str(getattr(proposal, "target", "") or "")
            estimated_loc = int(getattr(proposal, "estimated_loc", 0) or 0)
            payload = getattr(proposal, "payload", {}) or {}
            if not isinstance(payload, dict):
                payload = {}

            # Conservative features for small code-evo proposals
            risk_flags: list[str] = list(self._recent_constitution_flags[-3:])
            risk_flags.extend(list(self._recent_risk_flags[-3:]))

            # Hard veto: forbidden targets / risk keys in payload
            forbidden_markers = (
                "lumina_core/risk",
                "final_arbitration",
                "order_gatekeeper",
                "broker",
                "max_risk_percent",
                "drawdown_kill_percent",
            )
            blob = f"{target}|{operator}|{json.dumps(payload, sort_keys=True, default=str)}"
            for m in forbidden_markers:
                if m in blob:
                    risk_flags.append(f"constitution_code_forbidden:{m}")

            # Size heuristic
            code = str(payload.get("code") or "")
            if len(code) > 4000 or estimated_loc > 40:
                risk_flags.append("constitution_code_too_large")

            # Prefer allow small sandbox-only targets
            features = {
                "bias": 1.0,
                "fitness": 1.0 if not risk_flags else 0.2,
                "mutation_rate": min(1.0, estimated_loc / 40.0),
                "generation": 0.0,
                "content_len_norm": min(1.0, len(code) / 4000.0) if code else 0.1,
                "high_fitness": 1.0 if not risk_flags else 0.0,
                "contains_risk_word": 1.0 if risk_flags else 0.0,
                "contains_safety_word": 0.6,
                "has_lineage": 1.0 if proposal_id else 0.0,
                "fomo_sens": 1.0,
                "tilt_sens": 1.0,
                "boredom_sens": 1.0,
                "revenge_sens": 1.0,
            }
            raw = self._score(features)
            score = self._calibrate(raw)
            recommendation = bool(score >= self._state.threshold and not risk_flags)
            if risk_flags:
                recommendation = False

            explanation = (
                f"code_proposal op={operator} target={target} loc={estimated_loc} "
                f"score={score:.2%} threshold={self._state.threshold:.0%} flags={risk_flags}"
            )
            decision = {
                "recommendation": recommendation,
                "confidence": round(float(score), 6),
                "explanation": explanation,
                "risk_flags": risk_flags,
                "proposal_id": proposal_id,
            }
            return self._finalize_and_publish_decision(
                decision,
                dna_hash=str(proposal_id or target),
                call="evaluate_code_proposal",
            )
