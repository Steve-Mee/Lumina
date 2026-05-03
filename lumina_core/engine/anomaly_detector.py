from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol

from ..evolution.meta_swarm import MetaSwarm, meta_swarm_governance_enabled, parallel_realities_from_config

from .audit_writer import AuditWriterProtocol


class _AnomalyOwner(Protocol):
    engine: Any
    auto_fine_tuning_enabled: bool
    min_acceptance_rate: float
    drift_threshold: float
    runtime_mode: str


class AnomalyDetectorProtocol(Protocol):
    def meta_review(self, report: dict[str, Any]) -> dict[str, Any]: ...

    def auto_fine_tuning_trigger(self, *, meta_review: dict[str, Any]) -> dict[str, Any]: ...

    def external_release_gates_ok(self) -> bool: ...

    def shadow_rollout_evidence_ok(self) -> bool: ...


class AnomalyDetector:
    def __init__(
        self,
        owner: _AnomalyOwner,
        audit_writer: AuditWriterProtocol,
        logger: logging.Logger | None = None,
    ) -> None:
        self._owner = owner
        self._audit_writer = audit_writer
        self._logger = logger or logging.getLogger(__name__)

    def acceptance_rate_3d(self) -> float:
        entries = self._audit_writer.entries_last_3_days()
        if not entries:
            return 1.0
        accepted = 0
        total = 0
        for item in entries:
            status = str(item.get("status", "")).lower()
            if status in {"proposed", "awaiting_human_approval", "applied", "approved", "auto_applied"}:
                total += 1
                if status in {"applied", "approved", "auto_applied"}:
                    accepted += 1
        return float(accepted / total) if total > 0 else 1.0

    def max_drift_3d_from_log(self) -> float:
        entries = self._audit_writer.entries_last_3_days()
        max_drift = 0.0
        for item in entries:
            meta_review = item.get("meta_review", {}) if isinstance(item.get("meta_review"), dict) else {}
            max_drift = max(
                max_drift,
                float(meta_review.get("rl_drift", 0.0) or 0.0),
                float(meta_review.get("regime_drift", 0.0) or 0.0),
            )
        return max_drift

    def compute_meta_review_metrics(self, report: dict[str, Any]) -> dict[str, Any]:
        trades = int(report.get("trades", 0) or 0)
        wins = int(report.get("wins", 0) or 0)
        win_rate = float(wins / trades) if trades > 0 else 0.0
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)

        regime_history = list(getattr(self._owner.engine, "regime_history", []) or [])
        regime_drift = self.compute_regime_drift(regime_history)
        rl_drift = self.compute_rl_drift(report)
        emotional_twin_accuracy = self.compute_emotional_twin_accuracy(self._owner.engine, report)

        return {
            "trades": trades,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "net_pnl": round(net_pnl, 4),
            "sharpe": round(sharpe, 4),
            "regime_drift": regime_drift,
            "regime_breakdown": self.regime_breakdown(report),
            "rl_drift": rl_drift,
            "emotional_twin_accuracy": emotional_twin_accuracy,
        }

    def meta_swarm_nightly_payload(self, report: dict[str, Any], base: dict[str, Any]) -> dict[str, Any]:
        if not meta_swarm_governance_enabled():
            return {
                "enabled": False,
                "allow_promotion": True,
                "collective_score": None,
                "risk_veto": False,
                "round_two": [],
            }
        health = float(self.dna_fitness(base))
        hours = int(report.get("sim_duration_hours", 24) or 24)
        sim_days = max(1, (hours + 23) // 24)
        ctx: dict[str, Any] = {
            "winner_fitness": health,
            "previous_fitness": health,
            "nightly_report": dict(report),
            "mode": str(self._owner.runtime_mode),
            "sim_days": sim_days,
            "parallel_realities": int(parallel_realities_from_config()),
            "generation": 0,
            "neuro_winner_accepted": False,
            "winner_prompt_id": "nightly_meta_review",
        }
        consensus = MetaSwarm().deliberate(ctx)
        return {
            "enabled": True,
            "allow_promotion": bool(consensus.allow_promotion),
            "collective_score": round(float(consensus.collective_score), 6),
            "risk_veto": bool(consensus.risk_veto),
            "challenge_log": list(consensus.challenge_log),
            "round_two": [
                {
                    "agent": v.agent_id,
                    "approve": bool(v.approve),
                    "score": round(float(v.score), 4),
                    "veto": bool(v.veto),
                }
                for v in consensus.round_two
            ],
        }

    def meta_review(self, report: dict[str, Any]) -> dict[str, Any]:
        base = self.compute_meta_review_metrics(report)
        base["meta_swarm"] = self.meta_swarm_nightly_payload(report, base)
        return base

    def external_release_gates_ok(self) -> bool:
        golden = Path("state/golden_path_baseline.json")
        slo = Path("state/slo_report.json")
        try:
            if not golden.exists() or not slo.exists():
                return False
            golden_payload = json.loads(golden.read_text(encoding="utf-8"))
            slo_payload = json.loads(slo.read_text(encoding="utf-8"))
            return int(golden_payload.get("return_code", 1)) == 0 and str(slo_payload.get("status", "")).lower() in {
                "ok",
                "pass",
                "green",
            }
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/anomaly_detector.py:155")
            return False

    def shadow_rollout_evidence_ok(self) -> bool:
        report = Path("state/validation/shadow_rollout_report.json")
        if not report.exists():
            return False
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
            return bool(payload.get("ready_for_promotion", False))
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/anomaly_detector.py:165")
            return False

    def auto_fine_tuning_trigger(self, *, meta_review: dict[str, Any]) -> dict[str, Any]:
        if not self._owner.auto_fine_tuning_enabled:
            return {
                "triggered": False,
                "reason": "auto fine-tuning disabled",
                "acceptance_rate_3d": 1.0,
                "drift_3d": 0.0,
            }
        acceptance_rate = self.acceptance_rate_3d()
        drift_3d = max(
            float(meta_review.get("rl_drift", 0.0) or 0.0),
            float(meta_review.get("regime_drift", 0.0) or 0.0),
            self.max_drift_3d_from_log(),
        )
        low_acceptance = acceptance_rate < self._owner.min_acceptance_rate
        high_drift = drift_3d > self._owner.drift_threshold
        return {
            "triggered": bool(low_acceptance or high_drift),
            "reason": (
                f"acceptance_rate_3d={acceptance_rate:.3f} < {self._owner.min_acceptance_rate:.3f}"
                if low_acceptance
                else f"drift_3d={drift_3d:.3f} > {self._owner.drift_threshold:.3f}"
                if high_drift
                else "thresholds healthy"
            ),
            "acceptance_rate_3d": round(acceptance_rate, 4),
            "drift_3d": round(drift_3d, 4),
        }

    @staticmethod
    def compute_regime_drift(regime_history: list[Any]) -> float:
        if not regime_history:
            return 0.5
        normalized = []
        for item in regime_history:
            if isinstance(item, dict):
                normalized.append(str(item.get("label") or item.get("regime") or item).upper())
            else:
                normalized.append(str(item).upper())
        unique = len(set(normalized))
        return min(1.0, unique / max(1.0, len(normalized) * 0.5))

    @staticmethod
    def regime_breakdown(report: dict[str, Any]) -> dict[str, Any]:
        attribution = report.get("regime_attribution", {})
        if not isinstance(attribution, dict):
            return {}
        return {
            str(regime): {
                "trades": float(stats.get("trades", 0.0) or 0.0),
                "net_pnl": float(stats.get("net_pnl", 0.0) or 0.0),
                "winrate": float(stats.get("winrate", 0.0) or 0.0),
            }
            for regime, stats in attribution.items()
            if isinstance(stats, dict)
        }

    @staticmethod
    def weakest_regime(meta_review: dict[str, Any]) -> str:
        breakdown = meta_review.get("regime_breakdown", {})
        if not isinstance(breakdown, dict) or not breakdown:
            return "neutral"
        weakest = min(
            breakdown.items(),
            key=lambda item: (float(item[1].get("net_pnl", 0.0)), float(item[1].get("winrate", 0.0))),
        )
        return str(weakest[0]).lower()

    @staticmethod
    def compute_rl_drift(report: dict[str, Any]) -> float:
        samples = report.get("samples", [])
        if not isinstance(samples, list) or not samples:
            return 0.5
        rewards = [float(item.get("reward", 0.0)) for item in samples if isinstance(item, dict)]
        if not rewards:
            return 0.5
        mean_abs = sum(abs(v) for v in rewards) / len(rewards)
        return max(0.0, min(1.0, mean_abs / 5.0))

    @staticmethod
    def compute_emotional_twin_accuracy(engine: Any, report: dict[str, Any]) -> float:
        et = getattr(engine, "emotional_twin", None)
        if et is not None and hasattr(et, "last_accuracy"):
            try:
                return max(0.0, min(1.0, float(getattr(et, "last_accuracy"))))
            except Exception:
                logging.exception("AnomalyDetector failed to read emotional_twin.last_accuracy")
        wins = int(report.get("wins", 0) or 0)
        trades = int(report.get("trades", 0) or 0)
        if trades <= 0:
            return 0.5
        return max(0.0, min(1.0, wins / trades))

    @staticmethod
    def dna_fitness(meta_review: dict[str, Any]) -> float:
        return round(
            float(meta_review.get("sharpe", 0.0) or 0.0)
            + float(meta_review.get("win_rate", 0.0) or 0.0)
            + float(meta_review.get("emotional_twin_accuracy", 0.0) or 0.0)
            - float(meta_review.get("regime_drift", 0.0) or 0.0)
            - float(meta_review.get("rl_drift", 0.0) or 0.0),
            6,
        )
