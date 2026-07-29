"""Approval Twin training metrics helpers + metrics() mixin (Wave B2 PR-C1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

DecisionKind = Literal["approve", "reject", "modify"]
StakesLevel = Literal["high", "routine"]

# Matches birth/autonomy high-conf band (organism_autonomy: conf >= 0.80 + clean).
HIGH_CONF_THRESHOLD = 0.80


def _tail_jsonl(path: Path, limit: int = 20) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        items: list[dict[str, Any]] = []
        for line in lines[-max(1, int(limit)) :]:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items
    except OSError:
        return []


def _score_of(item: dict[str, Any]) -> float | None:
    raw = item.get("score", item.get("confidence"))
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def compute_confidence_distribution(
    decisions: list[dict[str, Any]],
) -> dict[str, int]:
    """Bucket twin decision scores for birth/operator observability.

    Buckets: lt_50 | b50_60 | b60_80 | gte_80 | n (total scored rows).
    Aligns with high-conf autonomy band (gte_80 == conf >= 0.80).
    """
    buckets = {"lt_50": 0, "b50_60": 0, "b60_80": 0, "gte_80": 0, "n": 0}
    for item in decisions:
        score = _score_of(item)
        if score is None:
            continue
        buckets["n"] += 1
        if score < 0.50:
            buckets["lt_50"] += 1
        elif score < 0.60:
            buckets["b50_60"] += 1
        elif score < HIGH_CONF_THRESHOLD:
            buckets["b60_80"] += 1
        else:
            buckets["gte_80"] += 1
    return buckets


def compute_decision_outcome_counts(
    decisions: list[dict[str, Any]],
) -> dict[str, int]:
    """Count outcome labels (auto_approved / veto / deferred / other)."""
    counts: dict[str, int] = {"auto_approved": 0, "veto": 0, "deferred": 0, "other": 0}
    for item in decisions:
        outcome = str(item.get("outcome") or "").strip().lower()
        if outcome in counts:
            counts[outcome] += 1
        elif outcome:
            counts["other"] += 1
        else:
            counts["other"] += 1
    return counts


def compute_risk_flag_counts(
    decisions: list[dict[str, Any]],
    *,
    top_n: int = 10,
) -> dict[str, int]:
    """Top risk_flag frequencies from recent twin decisions."""
    tallies: dict[str, int] = {}
    for item in decisions:
        flags = item.get("risk_flags") or []
        if not isinstance(flags, list):
            continue
        for flag in flags:
            key = str(flag or "").strip()
            if not key:
                continue
            tallies[key] = tallies.get(key, 0) + 1
    ordered = sorted(tallies.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: v for k, v in ordered[: max(1, int(top_n))]}


def decision_to_answer(decision: DecisionKind, notes: str = "") -> str:
    note = str(notes or "").strip()
    if decision == "approve":
        return "APPROVE" if not note else f"APPROVE: {note}"
    if decision == "reject":
        return "VETO" if not note else f"VETO: {note}"
    # modify
    return f"MODIFY: {note}" if note else "MODIFY"


def default_confidence(decision: DecisionKind) -> float:
    if decision == "approve":
        return 0.85
    if decision == "reject":
        return 0.25
    return 0.45


def build_vraag(
    *,
    dna_hash: str,
    twin_score: float | None,
    twin_recommendation: bool | None,
    explanation: str,
    risk_flags: list[str] | None,
    notes: str = "",
) -> str:
    score_s = f"{float(twin_score):.2%}" if twin_score is not None else "n/a"
    rec_s = str(bool(twin_recommendation)) if twin_recommendation is not None else "n/a"
    expl = str(explanation or "")[:200]
    risks = list(risk_flags or [])
    parts = [
        f"Twin decision review: dna={dna_hash} score={score_s} rec={rec_s}",
        f"risks={risks}",
        expl,
    ]
    note = str(notes or "").strip()
    if note:
        parts.append(f"steve_note={note}")
    return " | ".join(p for p in parts if p)


def classify_stakes(item: dict[str, Any]) -> StakesLevel:
    """High-stakes = risk flags, mid/low score, or approve-with-risks. Else routine."""
    risks = item.get("risk_flags") or []
    risk_list = [str(r) for r in risks] if isinstance(risks, list) else []
    if risk_list:
        return "high"
    score = _score_of(item)
    if score is None:
        return "high"
    if score < HIGH_CONF_THRESHOLD:
        return "high"
    return "routine"


def annotate_review_item(
    item: dict[str, Any],
    *,
    labeled_hashes: set[str],
) -> dict[str, Any]:
    """Copy decision row and attach UI/API metadata (stakes, already_labeled)."""
    out = dict(item)
    dna = str(out.get("dna_hash") or "").strip()
    out["already_labeled"] = bool(dna and dna in labeled_hashes)
    out["stakes"] = classify_stakes(out)
    return out


class TwinTrainingMetricsMixin:
    """metrics() rollup for TwinTrainingService."""

    def metrics(
        self,
        *,
        decision_window: int = 200,
        series_limit: int = 30,
    ) -> dict[str, Any]:
        latest: dict[str, Any] = {}
        items = _tail_jsonl(self.training_path, limit=1)  # type: ignore[attr-defined]
        if items:
            latest = items[-1]

        model: dict[str, Any] = {}
        if self.model_path.exists():  # type: ignore[attr-defined]
            try:
                parsed = json.loads(self.model_path.read_text(encoding="utf-8"))  # type: ignore[attr-defined]
                if isinstance(parsed, dict):
                    model = parsed
            except (OSError, json.JSONDecodeError):
                model = {}

        agreement: float | None
        try:
            agreement = float(self.twin.compute_steve_agreement_pct(limit=100))  # type: ignore[attr-defined]
        except Exception:
            agreement = None

        labels_sample = self.registry.list_recent(limit=500)  # type: ignore[attr-defined]

        mode_metrics: dict[str, Any] = {}
        mode_status: dict[str, Any] = {}
        try:
            if hasattr(self.twin, "observation_metrics"):  # type: ignore[attr-defined]
                mode_metrics = dict(self.twin.observation_metrics() or {})  # type: ignore[attr-defined]
            if hasattr(self.twin, "mode_status"):  # type: ignore[attr-defined]
                mode_status = dict(self.twin.mode_status() or {})  # type: ignore[attr-defined]
            elif hasattr(self.twin, "metrics_store"):  # type: ignore[attr-defined]
                mode_metrics["durable_metrics"] = self.twin.metrics_store.metrics_dict()  # type: ignore[attr-defined]
        except Exception:
            pass

        durable = mode_metrics.get("durable_metrics") if isinstance(mode_metrics, dict) else {}
        if not isinstance(durable, dict):
            durable = {}

        # Rich observability from durable TwinMetricsStore (agreement series, calib, progress)
        obs: dict[str, Any] = {}
        current_mode = str(
            mode_status.get("mode")
            or mode_metrics.get("mode")
            or getattr(self.twin, "mode", "shadow")  # type: ignore[attr-defined]
            or "shadow"
        )
        try:
            store = getattr(self.twin, "metrics_store", None)  # type: ignore[attr-defined]
            if store is not None and hasattr(store, "observability_bundle"):
                obs = dict(
                    store.observability_bundle(
                        current_mode=current_mode,
                        series_limit=max(1, int(series_limit)),
                        decision_limit=max(100, int(decision_window) * 3),
                    )
                    or {}
                )
                # Prefer store durable metrics when available (includes missed flags etc.)
                durable_from_obs = obs.get("durable_metrics")
                if isinstance(durable_from_obs, dict) and durable_from_obs:
                    durable = durable_from_obs
        except Exception:
            obs = {}

        recent_decisions = _tail_jsonl(
            self.decisions_path,  # type: ignore[attr-defined]
            limit=max(1, int(decision_window)),
        )
        confidence_distribution = compute_confidence_distribution(recent_decisions)
        outcome_counts = compute_decision_outcome_counts(recent_decisions)
        risk_flag_top = compute_risk_flag_counts(recent_decisions, top_n=10)

        calibration = obs.get("calibration") if isinstance(obs.get("calibration"), dict) else {}
        rolling = obs.get("rolling_agreement") if isinstance(obs.get("rolling_agreement"), dict) else {}
        mode_progress = (
            obs.get("mode_promotion_progress")
            if isinstance(obs.get("mode_promotion_progress"), dict)
            else {}
        )

        # Prefer durable Steve-label agreement when present
        steve_agree = durable.get("steve_label_agreement_pct")
        if steve_agree is None or (
            isinstance(steve_agree, (int, float)) and float(steve_agree) == 0.0
            and int(durable.get("steve_label_samples") or 0) == 0
        ):
            steve_agree = latest.get(
                "twin_steve_agreement_pct",
                latest.get("agreement_pct", agreement),
            )

        return {
            "avg_prediction_error": latest.get(
                "avg_prediction_error", model.get("last_avg_error", None)
            ),
            "reward": latest.get("reward", None),
            "training_steps": latest.get(
                "training_steps", model.get("training_steps", 0)
            ),
            "threshold": model.get("threshold", 0.6),
            "last_avg_error": model.get("last_avg_error", None),
            "twin_steve_agreement_pct": steve_agree,
            "samples": latest.get("samples", None),
            "labels_total_recent_cap": len(labels_sample),
            "model_path": str(self.model_path),  # type: ignore[attr-defined]
            "decisions_path": str(self.decisions_path),  # type: ignore[attr-defined]
            "training_path": str(self.training_path),  # type: ignore[attr-defined]
            "local_only": True,
            # Shadow mode / promotion gate metrics
            "mode": current_mode,
            "authority": mode_status.get("authority")
            or mode_metrics.get("authority")
            or mode_progress.get("authority"),
            "twin_agreement_pct": durable.get("agreement_pct", mode_metrics.get("agreement_pct")),
            "false_positives": durable.get("false_positives"),
            "false_positive_pct": durable.get("false_positive_pct"),
            "false_negatives": durable.get("false_negatives"),
            "risk_flags_caught": durable.get("risk_flags_caught"),
            "risk_flags_caught_pct": durable.get("risk_flags_caught_pct"),
            "risk_flags_missed": durable.get("risk_flags_missed"),
            "risk_flags_missed_pct": durable.get("risk_flags_missed_pct"),
            "risk_flags_catch_rate_pct": durable.get("risk_flags_catch_rate_pct"),
            "constitution_adherence_pct": durable.get("constitution_adherence_pct"),
            "mode_samples": durable.get("samples"),
            "mode_readiness": mode_status.get("readiness"),
            "mode_metrics": durable,
            # Birth / operator observability (decisions window)
            "decisions_total": len(recent_decisions),
            "decision_window": max(1, int(decision_window)),
            "confidence_distribution": confidence_distribution,
            "outcome_counts": outcome_counts,
            "risk_flag_top": risk_flag_top,
            # First-class Twin observability (agreement over time, calibration, promotion)
            "rolling_agreement": rolling,
            "agreement_over_time": list(obs.get("agreement_over_time") or []),
            "calibration": {
                **(calibration if isinstance(calibration, dict) else {}),
                "last_avg_error": model.get("last_avg_error", None),
            },
            "mode_promotion_progress": mode_progress,
            "promotion_audit_tail": list(obs.get("promotion_audit_tail") or []),
        }
