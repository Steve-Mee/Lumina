"""TwinModeController implementation."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
from lumina_core.evolution.twin_mode_promotion_gate_impl import TwinModePromotionGate
from lumina_core.evolution.twin_mode_types import (
    TwinModeName,
    TwinModePromotionDecision,
    TwinModePromotionEvidence,
    _DEFAULT_MODE_STATE,
    _MODE_RANK,
    _utcnow,
    authority_for_mode,
    canonicalize_twin_mode,
)

logger = logging.getLogger(__name__)

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
        # H4: never auto-jump to full_auto unless explicitly enabled (default off)
        self._auto_promote_full_auto = bool(promo.get("auto_promote_full_auto_when_ready", False))
        self._capital_mode = str(promo.get("capital_mode_hint") or twin_cfg.get("capital_mode") or "sim")
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
        # Track D: config.yaml may seed shadow/assisted only — full_auto requires gate promote.
        canonical = canonicalize_twin_mode(seed)
        if canonical == "full_auto":
            logger.warning(
                "twin_mode seed full_auto from config ignored — fail-closed to shadow "
                "(promote via TwinModePromotionGate only)"
            )
            return "shadow"
        return canonical

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

    def set_capital_mode_hint(self, capital_mode: str) -> None:
        """Runtime capital mode for full_auto safety (H4)."""
        self._capital_mode = str(capital_mode or "sim")

    def readiness(self, target_mode: str) -> TwinModePromotionDecision:
        snap = self._metrics.snapshot()
        base_trained = False
        try:
            from lumina_core.evolution.twin_base_training import is_twin_birth_ready

            base_trained = is_twin_birth_ready()
        except Exception:
            base_trained = False
        evidence = TwinModePromotionEvidence.from_snapshot(
            current_mode=self._mode,
            target_mode=target_mode,
            snap=snap,
            capital_mode=self._capital_mode,
            base_trained=base_trained,
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
        # H4 hard floor before gate eval
        if target == "full_auto":
            from lumina_core.evolution.twin_discipline import full_auto_allowed_for_capital_mode

            ok, reason = full_auto_allowed_for_capital_mode(self._capital_mode)
            if not ok:
                return {
                    "promoted": False,
                    "mode": current,
                    "target": target,
                    "reason": reason,
                    "fail_reasons": ["capital_mode_safe"],
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
        """Auto-promote one step only when configured; full_auto never auto by default (H4)."""
        if not self._auto_promote:
            return None
        if self._mode == "shadow":
            result = self.try_promote("assisted")
            return result if result.get("promoted") else None
        if self._mode == "assisted":
            if not self._auto_promote_full_auto:
                return None
            result = self.try_promote("full_auto")
            return result if result.get("promoted") else None
        return None

    def status(self) -> dict[str, Any]:
        snap = self._metrics.snapshot()
        assisted_ready = self.readiness("assisted")
        full_ready = self.readiness("full_auto")
        from lumina_core.evolution.twin_discipline import discipline_snapshot

        twin_cfg = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
        if not isinstance(twin_cfg, dict):
            twin_cfg = {}
        config_default = canonicalize_twin_mode(twin_cfg.get("mode") or "shadow")
        if config_default == "full_auto":
            config_default = "shadow"  # display clamp matches seed policy

        base = {
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
            "auto_promote_full_auto_when_ready": self._auto_promote_full_auto,
            "capital_mode_hint": self._capital_mode,
            # Track D mode SSOT: live = state file; config.yaml is seed only.
            "mode_ssot": {
                "live_mode": self._mode,
                "config_default_mode": config_default,
                "mode_state_path": str(self._mode_state_path),
                "mode_state_exists": self._mode_state_path.exists(),
                "authority": authority_for_mode(self._mode),
                "config_is_seed_only": True,
                "full_auto_requires_promotion_gate": True,
                "auto_promote_full_auto_default_off": not self._auto_promote_full_auto,
                "note": (
                    "Live mode is state/approval_twin_mode.json (or mode_state_path). "
                    "config.yaml evolution.approval_twin.mode is seed only when state missing; "
                    "full_auto never seeds from yaml — promote via gate after labels."
                ),
            },
        }
        base["discipline"] = discipline_snapshot(
            twin_mode=self._mode,
            capital_mode=self._capital_mode,
            metrics=snap.to_dict(),
            readiness=base["readiness"],
            auto_promote_when_ready=self._auto_promote,
            auto_promote_full_auto=self._auto_promote_full_auto,
        )
        return base
