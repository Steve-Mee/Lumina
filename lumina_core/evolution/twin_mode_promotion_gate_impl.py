"""TwinModePromotionGate implementation."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.twin_mode_types import (
    TwinModeCriterion,
    TwinModeCriterionResult,
    TwinModeName,
    TwinModePromotionDecision,
    TwinModePromotionEvidence,
    _DEFAULT_AUDIT_PATH,
    _MODE_RANK,
    _STREAM_NAME,
    _utcnow,
    canonicalize_twin_mode,
)

logger = logging.getLogger(__name__)

class TwinModePromotionGate:
    """Hard gate for twin mode upgrades. Fail-closed on missing evidence."""

    def __init__(
        self,
        *,
        audit_path: Path | None = None,
        config_section: str = "mode_promotion",
    ) -> None:
        cfg = self._resolve_config(config_section=config_section)
        self._min_samples_assisted = max(1, int(cfg.get("min_samples_assisted", 30)))
        self._min_agreement_assisted = float(cfg.get("min_agreement_pct_assisted", 80.0))
        self._max_fp_assisted = float(cfg.get("max_false_positive_pct_assisted", 10.0))
        self._min_samples_full_auto = max(1, int(cfg.get("min_samples_full_auto", 50)))
        self._min_agreement_full_auto = float(cfg.get("min_agreement_pct_full_auto", 90.0))
        self._max_fp_full_auto = float(cfg.get("max_false_positive_pct_full_auto", 5.0))
        self._min_risk_flags_caught_assisted = int(cfg.get("min_risk_flags_caught_assisted", 0))
        self._min_risk_flags_caught_full_auto = int(cfg.get("min_risk_flags_caught_full_auto", 1))
        self._require_constitution_100 = bool(cfg.get("require_constitution_adherence_100", True))
        # H4 training discipline
        self._min_steve_labels_assisted = max(0, int(cfg.get("min_steve_labels_assisted", 15)))
        self._min_steve_labels_full_auto = max(0, int(cfg.get("min_steve_labels_full_auto", 40)))
        self._forbid_full_auto_in_real_capital = bool(
            cfg.get("forbid_full_auto_in_real_capital", True)
        )
        self._audit_path = audit_path or Path(
            str(cfg.get("audit_path", _DEFAULT_AUDIT_PATH))
        )
        get_audit_logger().register_stream(_STREAM_NAME, self._audit_path)

    @staticmethod
    def _resolve_config(*, config_section: str) -> dict[str, Any]:
        twin_cfg = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
        if not isinstance(twin_cfg, dict):
            return {}
        promo = twin_cfg.get(config_section, {})
        return promo if isinstance(promo, dict) else {}

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "min_samples_assisted": self._min_samples_assisted,
            "min_agreement_pct_assisted": self._min_agreement_assisted,
            "max_false_positive_pct_assisted": self._max_fp_assisted,
            "min_samples_full_auto": self._min_samples_full_auto,
            "min_agreement_pct_full_auto": self._min_agreement_full_auto,
            "max_false_positive_pct_full_auto": self._max_fp_full_auto,
            "min_risk_flags_caught_assisted": self._min_risk_flags_caught_assisted,
            "min_risk_flags_caught_full_auto": self._min_risk_flags_caught_full_auto,
            "require_constitution_adherence_100": self._require_constitution_100,
            "min_steve_labels_assisted": self._min_steve_labels_assisted,
            "min_steve_labels_full_auto": self._min_steve_labels_full_auto,
            "forbid_full_auto_in_real_capital": self._forbid_full_auto_in_real_capital,
        }

    def evaluate(self, evidence: TwinModePromotionEvidence) -> TwinModePromotionDecision:
        current = canonicalize_twin_mode(evidence.current_mode)
        target = canonicalize_twin_mode(evidence.target_mode)

        criteria: list[TwinModeCriterionResult] = []
        criteria.append(self._evaluate_mode_order(current=current, target=target))

        if target == "shadow":
            # Demotion / stay at base is always allowed (fail-closed safety).
            criteria.append(
                TwinModeCriterionResult(
                    criterion=TwinModeCriterion.SAMPLE_SIZE,
                    passed=True,
                    score=1.0,
                    threshold=0.0,
                    actual=float(evidence.samples),
                    reason="shadow_is_base_mode",
                )
            )
        else:
            min_samples, min_agree, max_fp, min_caught = self._thresholds_for(target)
            criteria.append(self._evaluate_sample_size(evidence.samples, min_samples))
            criteria.append(self._evaluate_agreement(evidence.agreement_pct, min_agree))
            criteria.append(self._evaluate_false_positive(evidence.false_positive_pct, max_fp))
            criteria.append(
                self._evaluate_constitution(
                    evidence.constitution_adherence_pct,
                    evidence.constitution_violations,
                )
            )
            criteria.append(
                self._evaluate_risk_flags_caught(evidence.risk_flags_caught, min_caught)
            )
            # H4: steve-label training discipline
            min_steve = (
                self._min_steve_labels_full_auto
                if target == "full_auto"
                else self._min_steve_labels_assisted
            )
            criteria.append(
                self._evaluate_steve_labels(evidence.steve_label_samples, min_steve)
            )
            # H4: never promote to full_auto under REAL capital mode
            if target == "full_auto" and self._forbid_full_auto_in_real_capital:
                criteria.append(
                    self._evaluate_capital_mode_safe(str(getattr(evidence, "capital_mode", "sim") or "sim"))
                )

        fail_reasons = tuple(c.criterion.value for c in criteria if not c.passed)
        promoted = len(fail_reasons) == 0
        decision = TwinModePromotionDecision(
            current_mode=current,
            target_mode=target,
            promoted=promoted,
            criteria=criteria,
            timestamp=_utcnow(),
            config_snapshot=self._config_snapshot(),
            fail_reasons=fail_reasons,
            reason="ok" if promoted else "criteria_failed:" + ",".join(fail_reasons),
        )
        self._append_audit(decision=decision, evidence=evidence)
        return decision

    def _thresholds_for(self, target: TwinModeName) -> tuple[int, float, float, int]:
        if target == "full_auto":
            return (
                self._min_samples_full_auto,
                self._min_agreement_full_auto,
                self._max_fp_full_auto,
                self._min_risk_flags_caught_full_auto,
            )
        return (
            self._min_samples_assisted,
            self._min_agreement_assisted,
            self._max_fp_assisted,
            self._min_risk_flags_caught_assisted,
        )

    def _evaluate_mode_order(
        self, *, current: TwinModeName, target: TwinModeName
    ) -> TwinModeCriterionResult:
        cur_r = _MODE_RANK.get(current, 0)
        tgt_r = _MODE_RANK.get(target, 0)
        # Allow same-mode re-eval, one-step upgrade, or any demotion.
        if tgt_r <= cur_r:
            passed = True
            reason = "demotion_or_same_allowed"
        elif tgt_r == cur_r + 1:
            passed = True
            reason = "single_step_upgrade"
        else:
            passed = False
            reason = f"cannot_skip_steps:{current}->{target}"
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.MODE_ORDER,
            passed=passed,
            score=1.0 if passed else 0.0,
            threshold=float(cur_r + 1),
            actual=float(tgt_r),
            reason=reason,
            metadata={"current": current, "target": target},
        )

    def _evaluate_sample_size(self, samples: int, minimum: int) -> TwinModeCriterionResult:
        passed = int(samples) >= int(minimum)
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.SAMPLE_SIZE,
            passed=passed,
            score=min(1.0, float(samples) / float(max(1, minimum))),
            threshold=float(minimum),
            actual=float(samples),
            reason="ok" if passed else f"samples_lt_{minimum}",
        )

    def _evaluate_agreement(self, pct: float, minimum: float) -> TwinModeCriterionResult:
        passed = float(pct) >= float(minimum)
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.AGREEMENT,
            passed=passed,
            score=min(1.0, float(pct) / 100.0),
            threshold=float(minimum),
            actual=float(pct),
            reason="ok" if passed else f"agreement_pct_lt_{minimum}",
        )

    def _evaluate_false_positive(self, pct: float, maximum: float) -> TwinModeCriterionResult:
        # Fail-closed: if no samples, snapshot should already report 100% FP.
        passed = float(pct) <= float(maximum)
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.FALSE_POSITIVE,
            passed=passed,
            score=max(0.0, 1.0 - float(pct) / 100.0),
            threshold=float(maximum),
            actual=float(pct),
            reason="ok" if passed else f"false_positive_pct_gt_{maximum}",
        )

    def _evaluate_constitution(
        self, adherence_pct: float, violations: int
    ) -> TwinModeCriterionResult:
        if self._require_constitution_100:
            passed = int(violations) == 0 and float(adherence_pct) >= 100.0
        else:
            passed = int(violations) == 0
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.CONSTITUTION_ADHERENCE,
            passed=passed,
            score=1.0 if passed else 0.0,
            threshold=100.0,
            actual=float(adherence_pct),
            reason="ok" if passed else "constitution_adherence_failed",
            metadata={"violations": int(violations)},
        )

    def _evaluate_risk_flags_caught(
        self, caught: int, minimum: int
    ) -> TwinModeCriterionResult:
        passed = int(caught) >= int(minimum)
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.RISK_FLAGS_CAUGHT,
            passed=passed,
            score=min(1.0, float(caught) / float(max(1, minimum))) if minimum > 0 else 1.0,
            threshold=float(minimum),
            actual=float(caught),
            reason="ok" if passed else f"risk_flags_caught_lt_{minimum}",
        )

    def _evaluate_steve_labels(self, samples: int, minimum: int) -> TwinModeCriterionResult:
        passed = int(samples) >= int(minimum)
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.STEVE_LABELS,
            passed=passed,
            score=min(1.0, float(samples) / float(max(1, minimum))) if minimum > 0 else 1.0,
            threshold=float(minimum),
            actual=float(samples),
            reason="ok" if passed else f"steve_label_samples_lt_{minimum}",
        )

    def _evaluate_capital_mode_safe(self, capital_mode: str) -> TwinModeCriterionResult:
        from lumina_core.evolution.twin_discipline import is_real_like_capital

        unsafe = is_real_like_capital(capital_mode)
        passed = not unsafe
        return TwinModeCriterionResult(
            criterion=TwinModeCriterion.CAPITAL_MODE_SAFE,
            passed=passed,
            score=0.0 if unsafe else 1.0,
            threshold=1.0,
            actual=0.0 if unsafe else 1.0,
            reason="ok" if passed else f"full_auto_forbidden_in_capital:{capital_mode}",
            metadata={"capital_mode": str(capital_mode or "sim")},
        )

    def _append_audit(
        self,
        *,
        decision: TwinModePromotionDecision,
        evidence: TwinModePromotionEvidence,
    ) -> None:
        import os

        payload = {
            "event": "twin_mode_promotion_evaluated",
            "timestamp": decision.timestamp,
            "promoted": decision.promoted,
            "current_mode": decision.current_mode,
            "target_mode": decision.target_mode,
            "fail_reasons": list(decision.fail_reasons),
            "reason": decision.reason,
            "criteria": [c.model_dump(mode="json") for c in decision.criteria],
            "evidence": evidence.model_dump(mode="json"),
            "config_snapshot": decision.config_snapshot,
        }
        runtime_mode = str(os.getenv("LUMINA_MODE", "sim")).strip().lower() or "sim"
        try:
            get_audit_logger().append(
                stream=_STREAM_NAME,
                payload=payload,
                path=self._audit_path,
                mode=runtime_mode,
                actor_id="twin_mode_promotion_gate",
                severity="info",
            )
        except Exception:
            # Fallback direct append if audit logger unavailable
            try:
                self._audit_path.parent.mkdir(parents=True, exist_ok=True)
                with self._audit_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, sort_keys=True) + "\n")
            except Exception:
                logger.debug("twin_mode_promotion audit append failed", exc_info=True)
