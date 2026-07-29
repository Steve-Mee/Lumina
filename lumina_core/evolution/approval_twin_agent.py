"""Approval Twin agent — thin host + re-exports (Wave A PR5).

Bounded modules:
``approval_twin_backends``, ``approval_twin_bus``, ``approval_twin_scoring``,
``approval_twin_evaluators``, ``approval_twin_training``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.approval_twin_backends import (  # noqa: F401
    ApprovalTwinBackend,
    LocalHeuristicBackend,
    OllamaTwinBackend,
)
from lumina_core.evolution.approval_twin_bus import ApprovalTwinBusMixin
from lumina_core.evolution.approval_twin_evaluators import ApprovalTwinEvaluatorsMixin
from lumina_core.evolution.approval_twin_scoring import ApprovalTwinScoringMixin
from lumina_core.evolution.approval_twin_training import ApprovalTwinTrainingMixin
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
from lumina_core.evolution.twin_mode_promotion_gate import (
    TwinModeController,
    apply_mode_authority,
    canonicalize_twin_mode,
)
from lumina_core.logging_utils import (  # noqa: F401
    get_logger,
    record_shadow_twin_alignment_monitoring,
    record_twin_decision_monitoring,
    record_twin_steve_accuracy_monitoring,
    record_twin_training_metrics_monitoring,
)

logger = get_logger("lumina.evolution.twin")

# Canonical: shadow | assisted | full_auto (legacy advisory→assisted, active→full_auto)
_VALID_TWIN_MODES = frozenset({"shadow", "assisted", "full_auto", "advisory", "active"})


@dataclass(slots=True)
class ApprovalTwinState:
    intercept: float
    weights: dict[str, float]
    threshold: float
    training_steps: int
    # last_avg_error used for simple confidence calibration
    last_avg_error: float = 0.15


class ApprovalTwinAgent(
    ApprovalTwinBusMixin,
    ApprovalTwinEvaluatorsMixin,
    ApprovalTwinTrainingMixin,
    ApprovalTwinScoringMixin,
):
    """Small local approval model trained only on Steve's answers.

    This is the core of LUMINA's Approval Twin: a user-trained mimic that
    replaces human approval gates so the organism can evolve 24/7.
    """

    def __init__(
        self,
        *,
        registry: SteveValuesRegistry | None = None,
        model_path: Path | str = Path("state/approval_twin_model.json"),
        learning_rate: float = 0.08,
        backend: str | None = None,
        ollama_model: str | None = None,
        engine: Any = None,  # Optional: for risk shadow validation on risky DNA
        event_bus: EventBus | None = None,  # Optional central bus for typed Twin* events
        mode: str | None = None,  # shadow | assisted | full_auto (aliases: advisory, active)
        metrics_store: TwinMetricsStore | None = None,
        mode_controller: TwinModeController | None = None,
    ) -> None:
        self._registry = registry
        self._model_path = Path(model_path)
        self._learning_rate = float(learning_rate)
        self._state = self._load_state()
        self._backend_name, self._backend = self._build_backend(backend=backend, ollama_model=ollama_model)
        self._engine = engine  # for Phase 2 Deliverable 5 risk shadow integration
        self._event_bus: EventBus | None = None
        self._subscription_tokens: list[str] = []
        self._metrics_store = metrics_store or TwinMetricsStore()
        self._mode_controller = mode_controller or TwinModeController(
            metrics_store=self._metrics_store,
            initial_mode=mode,
        )
        if mode is not None:
            # Explicit constructor mode (tests / overrides): force-sync controller.
            self._mode = self._resolve_mode(mode)
            try:
                self._mode_controller.force_set_mode(self._mode, reason="ctor_explicit_mode")
            except Exception:
                pass
        else:
            # Prefer persisted controller mode (fail-closed default shadow if missing).
            self._mode = self._resolve_mode(self._mode_controller.mode)
        # In-memory observe counters (CLI / metrics; best-effort)
        self.observations_total: int = 0
        self.agreements: int = 0
        self.disagreements: int = 0
        # Recent constitution / risk flags from bus (inform observe + optional context; never sole gate)
        self._recent_constitution_flags: list[str] = []
        self._recent_risk_flags: list[str] = []
        if event_bus is not None:
            self.bind_event_bus(event_bus)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def metrics_store(self) -> TwinMetricsStore:
        return self._metrics_store

    @property
    def mode_controller(self) -> TwinModeController:
        return self._mode_controller

    def set_mode(self, mode: str, *, force: bool = False) -> str:
        """Set judgment mode.

        Without force, upgrades must go through ``try_promote`` (fail-closed);
        demotions apply immediately. With force=True (tests / operator recovery),
        write mode directly without gate.
        """
        canonical = self._resolve_mode(mode)
        if force:
            self._mode_controller.force_set_mode(canonical, reason="set_mode_force")
            self._mode = self._mode_controller.mode
            return self._mode
        rank = {"shadow": 0, "assisted": 1, "full_auto": 2}
        if rank.get(canonical, 0) < rank.get(self._mode, 0):
            self._mode_controller.demote(canonical, reason="set_mode_demote")
            self._mode = self._mode_controller.mode
            return self._mode
        if canonical == self._mode:
            return self._mode
        result = self._mode_controller.try_promote(canonical)
        if result.get("promoted"):
            self._mode = self._mode_controller.mode
        return self._mode

    def try_promote(self, target_mode: str) -> dict[str, Any]:
        result = self._mode_controller.try_promote(target_mode)
        if result.get("promoted"):
            self._mode = self._mode_controller.mode
        self._publish_mode_promotion(result=result, target_mode=str(target_mode))
        return result

    def mode_status(self) -> dict[str, Any]:
        status = self._mode_controller.status()
        status["agent_mode"] = self._mode
        status["observation_metrics"] = self.observation_metrics()
        return status

    def sync_mode_from_controller(self) -> str:
        """Refresh agent mode from persisted controller (auto-demote + optional auto-promote).

        Fail-closed: demotion on metric breach always applies; promotion only when
        config auto_promote_when_ready is true and gate criteria pass.
        """
        demote = self._mode_controller.maybe_auto_demote()
        if demote and demote.get("mode"):
            self._mode = str(demote["mode"])
            self._publish_mode_promotion(result=demote, target_mode=str(demote.get("mode", "shadow")))
        else:
            self._mode = self._mode_controller.mode
        promote = self._mode_controller.maybe_auto_promote()
        if promote and promote.get("promoted") and promote.get("mode"):
            self._mode = str(promote["mode"])
            self._publish_mode_promotion(result=promote, target_mode=str(promote.get("mode", self._mode)))
        else:
            self._mode = self._mode_controller.mode
        return self._mode

    @staticmethod
    def _resolve_mode(mode: str | None) -> str:
        cfg = ConfigLoader.section("evolution", "approval_twin", default={})
        cfg = cfg if isinstance(cfg, dict) else {}
        raw = str(mode or cfg.get("mode") or "shadow").strip().lower()
        if raw not in _VALID_TWIN_MODES and raw not in ("",):
            return "shadow"
        return canonicalize_twin_mode(raw or "shadow")

    def apply_mode_authority(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Stamp mode authority fields; consumers must use effective_recommendation."""
        raw_rec = bool(decision.get("recommendation", False))
        auth = apply_mode_authority(raw_recommendation=raw_rec, mode=self._mode)
        out = dict(decision)
        out.update(auth)
        # Keep raw judgment under recommendation (auth already sets it from raw)
        out["recommendation"] = raw_rec
        out["mode"] = auth["mode"]
        out["authority"] = auth["authority"]
        out["executable"] = auth["executable"]
        out["effective_recommendation"] = auth["effective_recommendation"]
        return out

    def _load_state(self) -> ApprovalTwinState:
        if not self._model_path.exists():
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0, last_avg_error=0.15)
        try:
            payload = json.loads(self._model_path.read_text(encoding="utf-8"))
            return ApprovalTwinState(
                intercept=float(payload.get("intercept", 0.0) or 0.0),
                weights={str(k): float(v) for k, v in dict(payload.get("weights", {})).items()},
                threshold=max(0.5, min(0.95, float(payload.get("threshold", 0.6) or 0.6))),
                training_steps=int(payload.get("training_steps", 0) or 0),
                last_avg_error=float(payload.get("last_avg_error", 0.15) or 0.15),
            )
        except Exception:
            logger.exception(
                "Unhandled broad exception fallback in lumina_core/evolution/approval_twin_agent.py"
            )
            return ApprovalTwinState(intercept=0.0, weights={}, threshold=0.6, training_steps=0, last_avg_error=0.15)

    def _save_state(self) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "intercept": float(self._state.intercept),
            "weights": dict(self._state.weights),
            "threshold": float(self._state.threshold),
            "training_steps": int(self._state.training_steps),
            "last_avg_error": float(getattr(self._state, "last_avg_error", 0.15)),
            "last_updated": datetime.now().isoformat(),
        }
        self._model_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


__all__ = [
    "ApprovalTwinAgent",
    "ApprovalTwinBackend",
    "ApprovalTwinState",
    "LocalHeuristicBackend",
    "OllamaTwinBackend",
]
