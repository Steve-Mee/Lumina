from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .engine_ports import SupportsExecution


@dataclass(slots=True)
class ExecutionService:
    """Handles execution-side state transitions and RL proposal routing."""

    engine: SupportsExecution

    def update_performance_log(self, performance_log: list[dict[str, Any]], trade_data: dict[str, Any]) -> None:
        performance_log.append(
            {
                "ts": datetime.now().isoformat(),
                "signal": trade_data.get("signal"),
                "chosen_strategy": trade_data.get("chosen_strategy", "unknown"),
                "regime": trade_data.get("regime", "NEUTRAL"),
                "confluence": trade_data.get("confluence", 0),
                "pnl": trade_data.get("pnl", 0),
                "drawdown": trade_data.get("drawdown", 0),
            }
        )
        if len(performance_log) > 500:
            performance_log.pop(0)

    def apply_rl_live_decision(
        self,
        action_payload: dict[str, Any],
        current_price: float,
        regime: str,
        confidence_threshold: float,
    ) -> bool:
        if not bool(action_payload):
            return False
        signal = str(action_payload.get("signal", "HOLD")).upper()
        confidence = float(action_payload.get("confidence", 0.0))
        qty = int(action_payload.get("qty", 1))
        stop = float(action_payload.get("stop", 0.0))
        target = float(action_payload.get("target", 0.0))

        if signal not in {"BUY", "SELL", "HOLD"}:
            return False
        if signal == "HOLD" or confidence < confidence_threshold:
            return False

        if stop <= 0.0:
            stop = current_price * (0.997 if signal == "BUY" else 1.003)
        if target <= 0.0:
            rr = max(1.2, min(3.0, 1.0 + confidence * 1.8))
            if signal == "BUY":
                target = current_price + (current_price - stop) * rr
            else:
                target = current_price - (stop - current_price) * rr

        updates = {
            "signal": signal,
            "confidence": confidence,
            "confluence_score": confidence,
            "stop": round(float(stop), 2),
            "target": round(float(target), 2),
            "reason": str(action_payload.get("reason", "PPO policy decision")),
            "chosen_strategy": "ppo_live_policy",
            "regime": regime,
            "qty": qty,
            "policy_ts": time.time(),
        }
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "add_proposal"):
            blackboard.add_proposal(
                topic="agent.rl.proposal",
                producer="rl_policy",
                payload=updates,
                confidence=confidence,
            )
        else:
            self.engine.set_current_dream_fields(updates)
        return True
