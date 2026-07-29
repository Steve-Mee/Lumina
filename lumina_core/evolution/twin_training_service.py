"""Shared Approval Twin training loop (CLI + FastAPI).

Keeps Steve's labels local and auditable:
  - state/steve_values_registry.sqlite3 + .jsonl (append-only)
  - state/approval_twin_model.json (light RLHF weights)
  - state/monitoring_twin_decisions.jsonl / monitoring_twin_training.jsonl

Does **not** touch promotion, REAL capital paths, or hard safety gates.

Gym sessions: ``twin_gym_session.TwinGymSessionMixin``.
Metrics rollups: ``twin_training_metrics.TwinTrainingMetricsMixin``.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry
from lumina_core.evolution.twin_gym_session import TwinGymSessionMixin
from lumina_core.evolution.twin_training_metrics import (  # noqa: F401
    HIGH_CONF_THRESHOLD,
    DecisionKind,
    StakesLevel,
    TwinTrainingMetricsMixin,
    _tail_jsonl,
    annotate_review_item,
    build_vraag,
    classify_stakes,
    compute_confidence_distribution,
    compute_decision_outcome_counts,
    compute_risk_flag_counts,
    decision_to_answer,
    default_confidence,
)

STATE_DIR = Path("state")
DEFAULT_TWIN_DECISIONS = STATE_DIR / "monitoring_twin_decisions.jsonl"
DEFAULT_TWIN_TRAINING = STATE_DIR / "monitoring_twin_training.jsonl"
DEFAULT_MODEL_PATH = STATE_DIR / "approval_twin_model.json"

# How far back in the registry we look when filtering already-labeled DNA.
LABELED_LOOKBACK = 2000


class TwinTrainingService(TwinGymSessionMixin, TwinTrainingMetricsMixin):
    """Orchestrate review queue, Steve labels, and light RLHF updates."""

    def __init__(
        self,
        *,
        registry: SteveValuesRegistry | None = None,
        twin: ApprovalTwinAgent | None = None,
        model_path: Path | str = DEFAULT_MODEL_PATH,
        decisions_path: Path | str = DEFAULT_TWIN_DECISIONS,
        training_path: Path | str = DEFAULT_TWIN_TRAINING,
    ) -> None:
        self.model_path = Path(model_path)
        self.decisions_path = Path(decisions_path)
        self.training_path = Path(training_path)
        self.registry = registry or SteveValuesRegistry()
        self.twin = twin or ApprovalTwinAgent(registry=self.registry, model_path=self.model_path)
        # Ensure twin sees the same registry instance
        if getattr(self.twin, "_registry", None) is None:
            self.twin._registry = self.registry  # noqa: SLF001 — intentional bind

    def _labeled_dna_hashes(self, *, lookback: int = LABELED_LOOKBACK) -> set[str]:
        records = self.registry.list_recent(limit=max(1, int(lookback)))
        return {
            str(r.context_dna_hash).strip()
            for r in records
            if str(getattr(r, "context_dna_hash", "") or "").strip()
        }

    def list_review_queue(
        self,
        *,
        limit: int = 20,
        include_labeled: bool = False,
    ) -> list[dict[str, Any]]:
        """Recent twin decisions for Steve review.

        By default excludes DNA already labeled in the local SteveValues registry.
        High-stakes items (risk flags / sub high-conf score) sort first; then newest.
        """
        # Over-fetch so filtering still yields up to `limit` unlabeled items.
        fetch_n = max(1, int(limit)) * (4 if not include_labeled else 1)
        fetch_n = min(500, max(fetch_n, int(limit)))
        raw = _tail_jsonl(self.decisions_path, limit=fetch_n)
        # Newest first before stakes re-sort
        newest_first = list(reversed(raw))

        labeled = self._labeled_dna_hashes()
        annotated: list[dict[str, Any]] = []
        for item in newest_first:
            row = annotate_review_item(item, labeled_hashes=labeled)
            if not include_labeled and row.get("already_labeled"):
                continue
            annotated.append(row)

        # High stakes first; within same stakes band keep newest-first order (stable).
        annotated.sort(key=lambda r: 0 if r.get("stakes") == "high" else 1)
        return annotated[: max(1, int(limit))]

    def list_labels(self, *, limit: int = 50) -> list[dict[str, Any]]:
        records = self.registry.list_recent(limit=max(1, int(limit)))
        return [asdict(r) for r in records]

    def record_decision(
        self,
        *,
        decision: DecisionKind,
        dna_hash: str,
        notes: str = "",
        twin_score: float | None = None,
        twin_recommendation: bool | None = None,
        explanation: str = "",
        risk_flags: list[str] | None = None,
        confidence_score: float | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        dna = str(dna_hash or "").strip()
        if not dna:
            raise ValueError("dna_hash is required")
        if decision not in ("approve", "reject", "modify"):
            raise ValueError(f"invalid decision: {decision}")

        answer = decision_to_answer(decision, notes)
        conf = (
            max(0.0, min(1.0, float(confidence_score)))
            if confidence_score is not None
            else default_confidence(decision)
        )
        vraag = build_vraag(
            dna_hash=dna,
            twin_score=twin_score,
            twin_recommendation=twin_recommendation,
            explanation=explanation,
            risk_flags=risk_flags,
            notes=notes,
        )
        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=answer,
            context_dna_hash=dna,
            confidence_score=conf,
        )
        self.registry.append(record)

        # Durable twin mode metrics: Steve label vs twin proposal (promotion evidence)
        steve_approve = decision == "approve"
        if hasattr(self.twin, "record_steve_label_comparison"):
            try:
                self.twin.record_steve_label_comparison(
                    twin_recommendation=twin_recommendation,
                    steve_approve=steve_approve,
                    risk_flags=list(risk_flags or []),
                    dna_hash=dna,
                    twin_confidence=twin_score,
                    steve_label=answer[:64],
                )
            except Exception:
                pass

        result: dict[str, Any] = {
            "recorded": True,
            "decision": decision,
            "label": answer,
            "record": asdict(record),
            "local_only": True,
            "audit": {
                "registry_sqlite": str(self.registry.sqlite_path),
                "registry_jsonl": str(self.registry.jsonl_path),
                "model_path": str(self.model_path),
            },
            "rlhf": None,
            "metrics": None,
        }

        if train_now:
            result["rlhf"] = self.twin.rlhf_light_update(records=[record])
            result["metrics"] = self.metrics()

        return result

    def train(self, *, limit: int = 250) -> dict[str, Any]:
        res = self.twin.fine_tune_from_registry(limit=max(1, int(limit)))
        return {
            "trained": bool(res.get("updated")),
            "result": res,
            "metrics": self.metrics(),
            "local_only": True,
            "audit": {
                "registry_sqlite": str(self.registry.sqlite_path),
                "registry_jsonl": str(self.registry.jsonl_path),
                "model_path": str(self.model_path),
            },
        }

    def promote_mode(self, target: str) -> dict[str, Any]:
        """Fail-closed twin mode promotion via gate."""
        if not hasattr(self.twin, "try_promote"):
            return {"promoted": False, "reason": "twin_missing_try_promote"}
        return self.twin.try_promote(target)

    def mode_status(self) -> dict[str, Any]:
        if hasattr(self.twin, "mode_status"):
            out = dict(self.twin.mode_status() or {})
        else:
            out = {"mode": getattr(self.twin, "mode", "shadow")}
        # Attach read-only promotion progress for Command Deck / birth
        try:
            store = getattr(self.twin, "metrics_store", None)
            if store is not None and hasattr(store, "mode_promotion_progress"):
                out["mode_promotion_progress"] = store.mode_promotion_progress(
                    current_mode=str(out.get("mode") or "shadow"),
                )
        except Exception:
            pass
        out.setdefault("local_only", True)
        return out
