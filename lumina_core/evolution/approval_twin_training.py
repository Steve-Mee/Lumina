"""Approval Twin RLHF / fine-tune / Steve agreement helpers."""
from __future__ import annotations

from lumina_core.evolution.approval_twin_patch_bridge import twin_attr

from typing import Any

from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.logging_utils import (
    get_logger,
    record_twin_steve_accuracy_monitoring,
    record_twin_training_metrics_monitoring,
)

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinTrainingMixin:
    def record_steve_label_comparison(
        self,
        *,
        twin_recommendation: bool | None,
        steve_approve: bool,
        risk_flags: list[str] | None = None,
        dna_hash: str = "",
        twin_confidence: float | None = None,
        steve_label: str = "",
    ) -> None:
        """Record human label vs twin proposal for promotion evidence."""
        if twin_recommendation is None:
            return
        try:
            self._metrics_store.record_comparison(
                twin_recommendation=bool(twin_recommendation),
                ground_truth_approve=bool(steve_approve),
                source="steve_label",
                risk_flags=list(risk_flags or []),
                dna_hash=str(dna_hash or ""),
                mode=self._mode,
                constitution_fatal=False,
                twin_confidence=twin_confidence,
                steve_label=str(steve_label or ""),
            )
        except Exception:
            pass

    def fine_tune_from_registry(self, *, limit: int = 250) -> dict[str, Any]:
        if self._registry is None:
            return {"updated": False, "reason": "registry_unavailable"}
        records = self._registry.list_recent(limit=max(1, int(limit)))
        return self.rlhf_light_update(records=records)

    def rlhf_light_update(self, *, records: list[SteveValueRecord]) -> dict[str, Any]:
        updates = 0
        abs_errors: list[float] = []

        # Replay from oldest to newest so recent Steve judgments dominate.
        for record in reversed(records):
            label = self._label_from_answer(record.steve_antwoord)
            if label is None:
                continue
            features = self._features_from_record(record)
            pred = self._score(features)
            error = float(label) - pred

            self._state.intercept += self._learning_rate * error
            for key, value in features.items():
                self._state.weights[key] = (
                    float(self._state.weights.get(key, 0.0)) + self._learning_rate * error * value
                )

            abs_errors.append(abs(error))
            updates += 1

        avg_error = sum(abs_errors) / len(abs_errors) if abs_errors else 1.0
        reward = max(0.0, min(1.0, 1.0 - avg_error))

        if updates > 0:
            self._state.training_steps += updates
            self._state.last_avg_error = float(avg_error)
            self._save_state()

        result = {
            "updated": updates > 0,
            "updates": updates,
            "avg_prediction_error": round(avg_error, 6),
            "reward": round(reward, 6),
            "training_steps": int(self._state.training_steps),
        }
        try:
            logger.info(
                "twin.rlhf_update",
                extra={
                    "event_data": {
                        "event": "twin.rlhf_update",
                        "records_processed": len(records),
                        "updates": updates,
                        "avg_prediction_error": result["avg_prediction_error"],
                        "reward": result["reward"],
                        "training_steps": result["training_steps"],
                    }
                },
            )
            twin_attr("record_twin_training_metrics_monitoring", record_twin_training_metrics_monitoring)(
                avg_prediction_error=float(result["avg_prediction_error"]),
                reward=float(result["reward"]),
                training_steps=int(result["training_steps"]),
            )
        except Exception:
            pass

        # Publish training update event (for every rlhf/fine-tune)
        self._publish_training_update(result=result, records_len=len(records))

        # Perfect Birth Phase KPI: twin accuracy vs Steve (label agreement %)
        try:
            agreement = self.compute_steve_agreement_pct(records=records)
            result["twin_steve_agreement_pct"] = agreement
            twin_attr("record_twin_steve_accuracy_monitoring", record_twin_steve_accuracy_monitoring)(
                agreement_pct=float(agreement),
                samples=len(records) or 0,
                avg_error=float(result.get("avg_prediction_error", 0.0) or 0.0),
            )
        except Exception:
            pass

        return result

    def compute_steve_agreement_pct(
        self, records: list[SteveValueRecord] | None = None, limit: int = 100
    ) -> float:
        """Compute direct agreement % between twin recommendation and Steve labels.

        This is the primary 'twin accuracy vs Steve' measurable success metric for
        Perfect Birth Phase. Replays current model (features + threshold) on records.
        Returns 0.0 if no usable labels.
        """
        if self._registry is None and not records:
            return 0.0
        try:
            recs: list[SteveValueRecord] = []
            if records:
                recs = list(records)
            elif self._registry is not None:
                recs = self._registry.list_recent(max(1, int(limit)))
            if not recs:
                return 0.0

            matches = 0
            total = 0
            thr = float(getattr(self._state, "threshold", 0.6) or 0.6)

            for r in recs:
                label = self._label_from_answer(getattr(r, "steve_antwoord", ""))
                if label is None:
                    continue
                feats = self._features_from_record(r)
                pred = self._score(feats)
                twin_rec = bool(pred >= thr)
                steve_rec = bool(label >= 0.5)
                if twin_rec == steve_rec:
                    matches += 1
                total += 1

            if total <= 0:
                return 0.0
            return round((matches / total) * 100.0, 2)
        except Exception:
            return 0.0
