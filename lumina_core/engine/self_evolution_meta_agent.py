from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lumina_engine import LuminaEngine
from .risk_controller import HardRiskController
from .valuation_engine import ValuationEngine


@dataclass(slots=True)
class SelfEvolutionMetaAgent:
    """Nightly self-evolution orchestrator for Lumina v50.

    Safety contract:
    - Never disables or bypasses RiskController.
    - Auto-apply is blocked when risk enforcement is not active.
    - All decisions are append-only logged with hash chaining.
    """

    engine: LuminaEngine
    valuation_engine: ValuationEngine
    risk_controller: HardRiskController | None
    enabled: bool = True
    approval_required: bool = True
    log_path: Path = field(default_factory=lambda: Path("state/evolution_log.jsonl"))
    obs_service: Any | None = None  # Optional ObservabilityService; injected at runtime

    @classmethod
    def from_container(
        cls,
        *,
        container: Any,
        enabled: bool = True,
        approval_required: bool = True,
        obs_service: Any | None = None,
    ) -> "SelfEvolutionMetaAgent":
        engine = getattr(container, "engine", None)
        if engine is None:
            raise ValueError("ApplicationContainer-like object must expose .engine")

        valuation_engine = getattr(container, "valuation_engine", None)
        if valuation_engine is None:
            valuation_engine = getattr(engine, "valuation_engine", ValuationEngine())

        risk_controller = getattr(container, "risk_controller", None)
        if risk_controller is None:
            risk_controller = getattr(engine, "risk_controller", None)

        return cls(
            engine=engine,
            valuation_engine=valuation_engine,
            risk_controller=risk_controller,
            enabled=enabled,
            approval_required=approval_required,
            obs_service=obs_service,
        )

    def run_nightly_evolution(self, *, nightly_report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        if not self.enabled:
            result = {
                "status": "disabled",
                "timestamp": now.isoformat(),
                "dry_run": dry_run,
            }
            self._append_immutable_log(result)
            return result

        meta_review = self._meta_review(nightly_report)
        champion = self._current_champion()
        challengers = self._build_challengers(champion)
        scored = [self._score_challenger(champion, c, nightly_report, meta_review) for c in challengers]
        best = max(scored, key=lambda item: float(item.get("score", 0.0))) if scored else None

        confidence = float(best.get("confidence", 0.0)) if best else 0.0
        backtest_green = self._backtest_green(nightly_report)
        safety_ok = self._safety_contract_ok()

        should_auto_apply = bool(confidence > 85.0 and backtest_green and safety_ok)
        approval_blocked = bool(self.approval_required and should_auto_apply)

        outcome = {
            "status": "awaiting_human_approval" if approval_blocked else ("proposed" if not should_auto_apply else "applied"),
            "timestamp": now.isoformat(),
            "dry_run": dry_run,
            "meta_review": meta_review,
            "champion": champion,
            "challengers": scored,
            "best_candidate": best,
            "proposal": {
                "confidence": round(confidence, 2),
                "backtest_green": backtest_green,
                "safety_ok": safety_ok,
                "approval_required": self.approval_required,
                "would_auto_apply": should_auto_apply,
                "auto_apply_executed": bool(should_auto_apply and not self.approval_required and not dry_run),
            },
        }

        if should_auto_apply and not self.approval_required and not dry_run and best is not None:
            self._apply_candidate(best)

        # Record proposal to observability metrics (no-op when obs_service is None)
        if self.obs_service is not None:
            try:
                best_name = str(best.get("name")) if best else None
                self.obs_service.record_evolution_proposal(
                    status=str(outcome.get("status", "unknown")),
                    confidence=confidence,
                    best_candidate=best_name,
                )
            except Exception:
                pass

        self._append_immutable_log(outcome)
        return outcome

    def _meta_review(self, report: dict[str, Any]) -> dict[str, Any]:
        trades = int(report.get("trades", 0) or 0)
        wins = int(report.get("wins", 0) or 0)
        win_rate = float(wins / trades) if trades > 0 else 0.0
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)

        regime_history = list(getattr(self.engine, "regime_history", []) or [])
        regime_drift = self._compute_regime_drift(regime_history)
        rl_drift = self._compute_rl_drift(report)
        emotional_twin_accuracy = self._compute_emotional_twin_accuracy(report)

        return {
            "trades": trades,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "net_pnl": round(net_pnl, 4),
            "sharpe": round(sharpe, 4),
            "regime_drift": regime_drift,
            "rl_drift": rl_drift,
            "emotional_twin_accuracy": emotional_twin_accuracy,
        }

    def _current_champion(self) -> dict[str, Any]:
        cfg = self.engine.config
        return {
            "name": "champion",
            "prompt_fingerprint": self._prompt_fingerprint(),
            "hyperparams": {
                "risk_profile": str(getattr(cfg, "risk_profile", "balanced")),
                "max_risk_percent": float(getattr(cfg, "max_risk_percent", 1.0)),
                "drawdown_kill_percent": float(getattr(cfg, "drawdown_kill_percent", 8.0)),
                "fast_path_threshold": float(getattr(cfg, "rl_confidence_threshold", 0.78) if hasattr(cfg, "rl_confidence_threshold") else 0.78),
            },
        }

    def _build_challengers(self, champion: dict[str, Any]) -> list[dict[str, Any]]:
        h = dict(champion.get("hyperparams", {}))
        base_threshold = float(h.get("fast_path_threshold", 0.78))
        base_risk = float(h.get("max_risk_percent", 1.0))
        base_dd = float(h.get("drawdown_kill_percent", 8.0))

        return [
            {
                "name": "challenger_a",
                "prompt_tweak": "More conservative under regime drift; prioritize HOLD when confidence split detected.",
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(min(0.9, base_threshold + 0.04), 3),
                    "max_risk_percent": round(max(0.3, base_risk * 0.9), 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.95), 3),
                },
            },
            {
                "name": "challenger_b",
                "prompt_tweak": "Increase trend-following bias when sharpe positive and RL drift low.",
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(max(0.6, base_threshold - 0.03), 3),
                    "max_risk_percent": round(min(2.0, base_risk * 1.05), 3),
                    "drawdown_kill_percent": round(min(15.0, base_dd * 1.02), 3),
                },
            },
            {
                "name": "challenger_c",
                "prompt_tweak": "Hybrid mode: strict risk gate + adaptive execution latency guard.",
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(base_threshold, 3),
                    "max_risk_percent": round(base_risk, 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.98), 3),
                },
            },
        ]

    def _score_challenger(
        self,
        champion: dict[str, Any],
        challenger: dict[str, Any],
        report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> dict[str, Any]:
        del champion

        win_rate = float(meta_review.get("win_rate", 0.0))
        sharpe = float(meta_review.get("sharpe", 0.0))
        regime_drift = float(meta_review.get("regime_drift", 0.5))
        rl_drift = float(meta_review.get("rl_drift", 0.5))
        emotional_accuracy = float(meta_review.get("emotional_twin_accuracy", 0.5))
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)

        quality = (
            (win_rate * 30.0)
            + (max(-1.0, min(2.0, sharpe)) * 8.0)
            + ((1.0 - regime_drift) * 12.0)
            + ((1.0 - rl_drift) * 12.0)
            + (emotional_accuracy * 10.0)
            + (8.0 if net_pnl > 0 else -8.0)
        )

        suggestion = challenger.get("hyperparam_suggestion", {})
        risk_penalty = 0.0
        if float(suggestion.get("max_risk_percent", 1.0)) > float(getattr(self.engine.config, "max_risk_percent", 1.0)):
            risk_penalty += 2.5
        if float(suggestion.get("drawdown_kill_percent", 8.0)) > float(getattr(self.engine.config, "drawdown_kill_percent", 8.0)):
            risk_penalty += 2.0

        score = max(0.0, quality - risk_penalty)
        confidence = max(0.0, min(99.0, 50.0 + score))

        out = dict(challenger)
        out["score"] = round(score, 4)
        out["confidence"] = round(confidence, 2)
        out["risk_penalty"] = round(risk_penalty, 2)
        return out

    def _backtest_green(self, report: dict[str, Any]) -> bool:
        trades = int(report.get("trades", 0) or 0)
        wins = int(report.get("wins", 0) or 0)
        win_rate = (wins / trades) if trades > 0 else 0.0
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)
        return bool(trades >= 50 and win_rate >= 0.45 and net_pnl > 0 and sharpe >= 0.2)

    def _safety_contract_ok(self) -> bool:
        if self.risk_controller is None:
            return False
        if not bool(getattr(self.risk_controller, "enforce_rules", False)):
            return False
        return True

    def _apply_candidate(self, candidate: dict[str, Any]) -> None:
        suggestion = dict(candidate.get("hyperparam_suggestion", {}))
        cfg = self.engine.config
        if "max_risk_percent" in suggestion:
            cfg.max_risk_percent = float(suggestion["max_risk_percent"])
        if "drawdown_kill_percent" in suggestion:
            cfg.drawdown_kill_percent = float(suggestion["drawdown_kill_percent"])

    def _prompt_fingerprint(self) -> str:
        agent_styles = dict(getattr(self.engine.config, "agent_styles", {}) or {})
        payload = json.dumps(agent_styles, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _compute_regime_drift(regime_history: list[Any]) -> float:
        if not regime_history:
            return 0.5
        normalized = [str(item).upper() for item in regime_history]
        unique = len(set(normalized))
        return min(1.0, unique / max(1.0, len(normalized) * 0.5))

    @staticmethod
    def _compute_rl_drift(report: dict[str, Any]) -> float:
        samples = report.get("samples", [])
        if not isinstance(samples, list) or not samples:
            return 0.5
        rewards = [float(item.get("reward", 0.0)) for item in samples if isinstance(item, dict)]
        if not rewards:
            return 0.5
        mean_abs = sum(abs(v) for v in rewards) / len(rewards)
        return max(0.0, min(1.0, mean_abs / 5.0))

    def _compute_emotional_twin_accuracy(self, report: dict[str, Any]) -> float:
        et = getattr(self.engine, "emotional_twin", None)
        if et is not None and hasattr(et, "last_accuracy"):
            try:
                return max(0.0, min(1.0, float(getattr(et, "last_accuracy"))))
            except Exception:
                pass
        wins = int(report.get("wins", 0) or 0)
        trades = int(report.get("trades", 0) or 0)
        if trades <= 0:
            return 0.5
        return max(0.0, min(1.0, wins / trades))

    def _append_immutable_log(self, entry: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = self._last_log_hash()
        payload = dict(entry)
        payload["prev_hash"] = prev_hash
        payload["log_version"] = "v1"
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["hash"] = payload_hash
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _last_log_hash(self) -> str:
        if not self.log_path.exists():
            return "GENESIS"
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            if not lines:
                return "GENESIS"
            last = json.loads(lines[-1])
            return str(last.get("hash", "GENESIS"))
        except Exception:
            return "GENESIS"


def load_evolution_config(config_path: str = "config.yaml") -> dict[str, Any]:
    try:
        import yaml

        if not os.path.exists(config_path):
            return {"enabled": True, "approval_required": True}
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        evo = data.get("evolution", {}) if isinstance(data, dict) else {}
        if not isinstance(evo, dict):
            evo = {}
        return {
            "enabled": bool(evo.get("enabled", True)),
            "approval_required": bool(evo.get("approval_required", True)),
        }
    except Exception:
        return {"enabled": True, "approval_required": True}
