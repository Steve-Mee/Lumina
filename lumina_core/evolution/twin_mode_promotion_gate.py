"""Fail-closed promotion gates for Approval Twin judgment authority.

Ladder: shadow → assisted → full_auto

The Twin may only advance when measurable criteria pass (agreement rate,
false-positive rate, constitution adherence, sample size). Missing evidence
is reject. Mode writes are audited.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lumina_core.audit import get_audit_logger
from lumina_core.config_loader import ConfigLoader

from .twin_metrics_store import TwinMetricsStore, TwinModeMetricsSnapshot

logger = logging.getLogger(__name__)

TwinModeName = Literal["shadow", "assisted", "full_auto"]

_VALID_MODES: frozenset[str] = frozenset({"shadow", "assisted", "full_auto"})
_MODE_ALIASES: dict[str, TwinModeName] = {
    "shadow": "shadow",
    "assisted": "assisted",
    "advisory": "assisted",
    "full_auto": "full_auto",
    "full-auto": "full_auto",
    "fullauto": "full_auto",
    "active": "full_auto",
}

_MODE_RANK: dict[str, int] = {"shadow": 0, "assisted": 1, "full_auto": 2}

_DEFAULT_MODE_STATE = Path("state/approval_twin_mode.json")
_DEFAULT_AUDIT_PATH = Path("state/twin_mode_promotion_audit.jsonl")
_STREAM_NAME = "evolution.twin_mode_promotion"

AuthorityName = Literal["propose_only", "veto_only", "execute_judgment"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_twin_mode(mode: str | None) -> TwinModeName:
    """Map raw/legacy mode to canonical. Invalid → shadow (fail-closed)."""
    raw = str(mode or "shadow").strip().lower()
    return _MODE_ALIASES.get(raw, "shadow")


def authority_for_mode(mode: str | None) -> AuthorityName:
    m = canonicalize_twin_mode(mode)
    if m == "full_auto":
        return "execute_judgment"
    if m == "assisted":
        return "veto_only"
    return "propose_only"


def apply_mode_authority(
    *,
    raw_recommendation: bool,
    mode: str | None,
) -> dict[str, Any]:
    """Compute executable / effective_recommendation from mode + raw judgment.

    - shadow: propose only — never auto-approve
    - assisted: veto blocks; approve does not sole-auto
    - full_auto: effective = raw recommendation
    """
    canonical = canonicalize_twin_mode(mode)
    authority = authority_for_mode(canonical)
    rec = bool(raw_recommendation)

    if canonical == "shadow":
        return {
            "mode": canonical,
            "authority": authority,
            "recommendation": rec,
            "executable": False,
            "effective_recommendation": False,
        }
    if canonical == "assisted":
        # Veto may block (effective False); approve cannot sole-execute.
        if not rec:
            return {
                "mode": canonical,
                "authority": authority,
                "recommendation": False,
                "executable": False,
                "effective_recommendation": False,
            }
        return {
            "mode": canonical,
            "authority": authority,
            "recommendation": True,
            "executable": False,
            "effective_recommendation": False,
        }
    # full_auto
    return {
        "mode": canonical,
        "authority": authority,
        "recommendation": rec,
        "executable": bool(rec),
        "effective_recommendation": rec,
    }


class TwinModeCriterion(str, Enum):
    SAMPLE_SIZE = "sample_size"
    AGREEMENT = "agreement"
    FALSE_POSITIVE = "false_positive"
    CONSTITUTION_ADHERENCE = "constitution_adherence"
    RISK_FLAGS_CAUGHT = "risk_flags_caught"
    MODE_ORDER = "mode_order"


class TwinModeCriterionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    criterion: TwinModeCriterion
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    threshold: float
    actual: float
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TwinModePromotionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_mode: TwinModeName = "shadow"
    target_mode: TwinModeName
    samples: int = Field(ge=0, default=0)
    agreement_pct: float = Field(ge=0.0, le=100.0, default=0.0)
    false_positive_pct: float = Field(ge=0.0, le=100.0, default=100.0)
    constitution_adherence_pct: float = Field(ge=0.0, le=100.0, default=0.0)
    risk_flags_caught: int = Field(ge=0, default=0)
    constitution_violations: int = Field(ge=0, default=0)
    steve_label_samples: int = Field(ge=0, default=0)
    path_samples: int = Field(ge=0, default=0)

    @classmethod
    def from_snapshot(
        cls,
        *,
        current_mode: str,
        target_mode: str,
        snap: TwinModeMetricsSnapshot,
    ) -> TwinModePromotionEvidence:
        return cls(
            current_mode=canonicalize_twin_mode(current_mode),
            target_mode=canonicalize_twin_mode(target_mode),
            samples=int(snap.samples),
            agreement_pct=float(snap.agreement_pct),
            false_positive_pct=float(snap.false_positive_pct if snap.samples > 0 else 100.0),
            constitution_adherence_pct=float(snap.constitution_adherence_pct),
            risk_flags_caught=int(snap.risk_flags_caught),
            constitution_violations=int(snap.constitution_violations),
            steve_label_samples=int(snap.steve_label_samples),
            path_samples=int(snap.path_samples),
        )


class TwinModePromotionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_mode: TwinModeName
    target_mode: TwinModeName
    promoted: bool
    criteria: list[TwinModeCriterionResult]
    timestamp: str
    config_snapshot: dict[str, Any]
    fail_reasons: tuple[str, ...]
    reason: str = ""


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


class TwinModeController:
    """Persist twin mode and apply promotion/demotion with fail-closed gates."""

    def __init__(
        self,
        *,
        mode_state_path: Path | str | None = None,
        gate: TwinModePromotionGate | None = None,
        metrics_store: TwinMetricsStore | None = None,
        initial_mode: str | None = None,
    ) -> None:
        twin_cfg = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
        if not isinstance(twin_cfg, dict):
            twin_cfg = {}
        promo = twin_cfg.get("mode_promotion") if isinstance(twin_cfg.get("mode_promotion"), dict) else {}
        self._mode_state_path = Path(
            mode_state_path
            or promo.get("mode_state_path")
            or twin_cfg.get("mode_state_path")
            or _DEFAULT_MODE_STATE
        )
        self._gate = gate or TwinModePromotionGate()
        self._metrics = metrics_store or TwinMetricsStore()
        self._demote_agreement_floor = float(promo.get("demote_agreement_floor_pct", 70.0))
        self._demote_fp_ceiling = float(promo.get("demote_false_positive_ceiling_pct", 20.0))
        self._auto_promote = bool(promo.get("auto_promote_when_ready", False))
        # Load persisted mode or seed from config/initial
        self._mode = self._load_mode(seed=initial_mode or twin_cfg.get("mode") or "shadow")

    @property
    def mode(self) -> TwinModeName:
        return self._mode

    def get_mode(self) -> TwinModeName:
        return self._mode

    def force_set_mode(self, mode: str, *, reason: str = "force_set") -> TwinModeName:
        """Write mode without promotion gate (ctor/tests/operator recovery only)."""
        canonical = canonicalize_twin_mode(mode)
        self._persist_mode(canonical, reason=reason)
        return self._mode

    def _load_mode(self, *, seed: str | None) -> TwinModeName:
        if self._mode_state_path.exists():
            try:
                payload = json.loads(self._mode_state_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return canonicalize_twin_mode(payload.get("mode"))
            except Exception:
                logger.debug("twin_mode_state load failed; using seed", exc_info=True)
        return canonicalize_twin_mode(seed)

    def _persist_mode(self, mode: TwinModeName, *, reason: str) -> None:
        self._mode_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": mode,
            "updated_at": _utcnow(),
            "reason": reason,
        }
        self._mode_state_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        self._mode = mode

    def readiness(self, target_mode: str) -> TwinModePromotionDecision:
        snap = self._metrics.snapshot()
        evidence = TwinModePromotionEvidence.from_snapshot(
            current_mode=self._mode,
            target_mode=target_mode,
            snap=snap,
        )
        return self._gate.evaluate(evidence)

    def try_promote(self, target_mode: str) -> dict[str, Any]:
        """Attempt upgrade to target. Fail-closed if gate rejects."""
        target = canonicalize_twin_mode(target_mode)
        current = self._mode
        if _MODE_RANK[target] < _MODE_RANK[current]:
            return self.demote(target, reason="explicit_demote")
        if target == current:
            return {
                "promoted": True,
                "mode": current,
                "reason": "already_at_mode",
                "decision": None,
            }
        decision = self.readiness(target)
        if not decision.promoted:
            return {
                "promoted": False,
                "mode": current,
                "target": target,
                "reason": decision.reason,
                "fail_reasons": list(decision.fail_reasons),
                "decision": decision.model_dump(mode="json"),
            }
        self._persist_mode(target, reason=f"promoted_from_{current}")
        return {
            "promoted": True,
            "mode": target,
            "previous_mode": current,
            "reason": "gate_passed",
            "decision": decision.model_dump(mode="json"),
        }

    def demote(self, target_mode: str = "shadow", *, reason: str = "demote") -> dict[str, Any]:
        target = canonicalize_twin_mode(target_mode)
        current = self._mode
        if _MODE_RANK[target] > _MODE_RANK[current]:
            return {
                "promoted": False,
                "mode": current,
                "reason": "demote_cannot_raise",
            }
        self._persist_mode(target, reason=reason)
        return {
            "promoted": True,
            "mode": target,
            "previous_mode": current,
            "reason": reason,
            "demoted": True,
        }

    def maybe_auto_demote(self) -> dict[str, Any] | None:
        """If metrics breach floors, drop one step (fail-closed)."""
        if self._mode == "shadow":
            return None
        snap = self._metrics.snapshot()
        if snap.samples < 10:
            return None  # avoid demote on thin noise
        breach = (
            snap.agreement_pct < self._demote_agreement_floor
            or snap.false_positive_pct > self._demote_fp_ceiling
            or snap.constitution_violations > 0
        )
        if not breach:
            return None
        new_mode: TwinModeName = "assisted" if self._mode == "full_auto" else "shadow"
        return self.demote(new_mode, reason="auto_demote_metrics_breach")

    def maybe_auto_promote(self) -> dict[str, Any] | None:
        if not self._auto_promote:
            return None
        if self._mode == "shadow":
            result = self.try_promote("assisted")
            return result if result.get("promoted") else None
        if self._mode == "assisted":
            result = self.try_promote("full_auto")
            return result if result.get("promoted") else None
        return None

    def status(self) -> dict[str, Any]:
        snap = self._metrics.snapshot()
        assisted_ready = self.readiness("assisted")
        full_ready = self.readiness("full_auto")
        return {
            "mode": self._mode,
            "authority": authority_for_mode(self._mode),
            "metrics": snap.to_dict(),
            "readiness": {
                "assisted": {
                    "promoted": assisted_ready.promoted,
                    "fail_reasons": list(assisted_ready.fail_reasons),
                    "reason": assisted_ready.reason,
                },
                "full_auto": {
                    "promoted": full_ready.promoted,
                    "fail_reasons": list(full_ready.fail_reasons),
                    "reason": full_ready.reason,
                },
            },
            "mode_state_path": str(self._mode_state_path),
            "auto_promote_when_ready": self._auto_promote,
        }
