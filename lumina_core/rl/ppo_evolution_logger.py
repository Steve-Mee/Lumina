"""PPO training evolution logger — JSONL metrics every N timesteps during SB3 learn()."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from lumina_core.logging_utils import _append_jsonl, resolve_monitoring_state_dir

try:
    from stable_baselines3.common.callbacks import BaseCallback
except ImportError:  # pragma: no cover
    BaseCallback = object  # type: ignore[misc, assignment]

ROLLING_WINDOW = 5000


@dataclass
class RollingStepMetrics:
    """Accumulates per-step training signals for rolling 5k aggregates."""

    window: int = ROLLING_WINDOW
    side_counts: dict[str, int] = field(default_factory=lambda: {"hold": 0, "long": 0, "short": 0})
    stop_pcts: deque[float] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))
    target_pcts: deque[float] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))
    trade_outcomes: deque[int] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))
    sharpe_samples: deque[float] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))
    equity_returns: deque[float] = field(default_factory=lambda: deque(maxlen=ROLLING_WINDOW))
    _last_equity: float | None = None

    def record_action(self, action: np.ndarray) -> None:
        arr = np.asarray(action, dtype=np.float32).reshape(-1)
        if arr.size == 0:
            return
        side_bucket = int(np.clip(np.round(float(arr[0])), 0, 2))
        if side_bucket == 0:
            self.side_counts["hold"] += 1
        elif side_bucket == 1:
            self.side_counts["long"] += 1
        else:
            self.side_counts["short"] += 1
        if arr.size > 2:
            self.stop_pcts.append(float(np.clip(arr[2], 0.001, 0.02)))
        if arr.size > 3:
            self.target_pcts.append(float(np.clip(arr[3], 0.001, 0.05)))

    def record_info(self, info: dict[str, Any]) -> None:
        gross_pnl = float(info.get("model_close_gross_pnl_usd", 0.0) or 0.0)
        if gross_pnl != 0.0:
            self.trade_outcomes.append(1 if gross_pnl > 0.0 else 0)

        sharpe = info.get("sharpe")
        if sharpe is not None:
            try:
                self.sharpe_samples.append(float(sharpe))
            except (TypeError, ValueError):
                pass

        equity = info.get("equity")
        if equity is not None:
            try:
                eq = float(equity)
            except (TypeError, ValueError):
                return
            if self._last_equity is not None and self._last_equity > 0.0:
                ret = (eq - self._last_equity) / self._last_equity
                self.equity_returns.append(float(ret))
            self._last_equity = eq


def compute_rolling_winrate(trade_outcomes: deque[int] | list[int]) -> float:
    if not trade_outcomes:
        return 0.0
    wins = sum(int(x) for x in trade_outcomes)
    return round(float(wins) / float(len(trade_outcomes)), 3)


def compute_rolling_sharpe(
    sharpe_samples: deque[float] | list[float],
    equity_returns: deque[float] | list[float],
) -> float:
    if sharpe_samples:
        return round(float(np.mean(np.asarray(list(sharpe_samples), dtype=np.float64))), 2)
    if len(equity_returns) < 2:
        return 0.0
    arr = np.asarray(list(equity_returns), dtype=np.float64)
    std = float(np.std(arr))
    if std <= 1e-12:
        return 0.0
    return round(float(np.mean(arr) / std * np.sqrt(len(arr))), 2)


def compute_action_distribution(side_counts: dict[str, int]) -> dict[str, float]:
    total = float(sum(max(0, int(v)) for v in side_counts.values()))
    if total <= 0.0:
        return {"long": 0.0, "short": 0.0, "hold": 0.0}
    return {
        "long": round(float(side_counts.get("long", 0)) / total, 2),
        "short": round(float(side_counts.get("short", 0)) / total, 2),
        "hold": round(float(side_counts.get("hold", 0)) / total, 2),
    }


def compute_avg_pct(values: deque[float] | list[float], default: float) -> float:
    if not values:
        return float(default)
    return round(float(np.mean(np.asarray(list(values), dtype=np.float64))), 4)


def _broadcast_entry_async(payload_json: str) -> None:
    try:
        from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer
    except ImportError:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    try:
        loop.create_task(ppo_realtime_tailer.broadcast_new_line(payload_json))
    except Exception:
        return


class PPOEvolutionLogger(BaseCallback):
    """Logs rich PPO training metrics to JSONL and optionally broadcasts live."""

    def __init__(
        self,
        log_path: str | Path | None = None,
        log_interval: int = 5000,
        verbose: int = 0,
    ) -> None:
        if BaseCallback is object:
            raise RuntimeError(
                "stable-baselines3 is required for PPOEvolutionLogger. "
                "Install with: pip install stable-baselines3"
            )
        super().__init__(verbose)
        default_path = resolve_monitoring_state_dir() / "ppo_training_log.jsonl"
        self.log_path = Path(log_path) if log_path is not None else default_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_interval = max(1, int(log_interval))
        self.last_log_step = 0
        self.last_entropy: float | None = None
        self._rolling = RollingStepMetrics(window=ROLLING_WINDOW)

    def _on_step(self) -> bool:
        self._accumulate_step()
        if int(self.num_timesteps) - self.last_log_step < self.log_interval:
            return True
        self._write_log_entry()
        self.last_log_step = int(self.num_timesteps)
        return True

    def _on_training_end(self) -> None:
        """Always flush once per learn() so short birth bursts still emit entropy."""
        if int(self.num_timesteps) <= 0:
            return
        if int(self.num_timesteps) == int(self.last_log_step):
            return
        self._write_log_entry()
        self.last_log_step = int(self.num_timesteps)

    def _accumulate_step(self) -> None:
        locals_map = getattr(self, "locals", None) or {}
        actions = locals_map.get("actions")
        infos = locals_map.get("infos")

        if actions is not None:
            action_arr = np.asarray(actions)
            if action_arr.ndim == 1:
                self._rolling.record_action(action_arr)
            else:
                for row in action_arr:
                    self._rolling.record_action(np.asarray(row))

        if infos is not None:
            for info in infos:
                if isinstance(info, dict):
                    self._rolling.record_info(info)

    def _sb3_logs(self) -> dict[str, float]:
        logger_obj = getattr(self.model, "logger", None)
        raw = getattr(logger_obj, "name_to_value", {}) if logger_obj is not None else {}
        return {str(k): float(v) for k, v in raw.items() if v is not None}

    @staticmethod
    def _resolve_policy_loss(logs: dict[str, float]) -> float:
        """SB3 2.8+ uses train/policy_gradient_loss; older builds used train/policy_loss."""
        if "train/policy_gradient_loss" in logs:
            return float(logs["train/policy_gradient_loss"])
        return float(logs.get("train/policy_loss", 0.0))

    @staticmethod
    def _resolve_entropy(logs: dict[str, float]) -> float:
        """SB3 2.8+ logs train/entropy_loss (negative mean entropy); older used train/entropy."""
        if "train/entropy_loss" in logs:
            # SB3 stores mean entropy as a loss term (negative); surface positive entropy.
            return float(-logs["train/entropy_loss"])
        return float(logs.get("train/entropy", 0.0))

    def _build_entry(self) -> dict[str, Any]:
        logs = self._sb3_logs()
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "step": int(self.num_timesteps),
            "mean_reward": float(logs.get("rollout/ep_rew_mean", 0.0)),
            "policy_loss": self._resolve_policy_loss(logs),
            "value_loss": float(logs.get("train/value_loss", 0.0)),
            "entropy": self._resolve_entropy(logs),
            "explained_variance": float(logs.get("train/explained_variance", 0.0)),
            "winrate_rolling_5k": self._get_rolling_winrate(),
            "sharpe_rolling_5k": self._get_rolling_sharpe(),
            "action_distribution": self._get_action_distribution(),
            "avg_stop_pct": self._get_avg_stop_pct(logs),
            "avg_target_pct": self._get_avg_target_pct(logs),
        }

    def _write_log_entry(self) -> None:
        entry = self._build_entry()
        try:
            self.last_entropy = float(entry["entropy"])
        except (KeyError, TypeError, ValueError):
            self.last_entropy = None
        _append_jsonl(self.log_path, entry)
        _broadcast_entry_async(json.dumps(entry, ensure_ascii=True, sort_keys=True))

    def _get_rolling_winrate(self) -> float:
        return compute_rolling_winrate(self._rolling.trade_outcomes)

    def _get_rolling_sharpe(self) -> float:
        return compute_rolling_sharpe(self._rolling.sharpe_samples, self._rolling.equity_returns)

    def _get_action_distribution(self) -> dict[str, float]:
        return compute_action_distribution(self._rolling.side_counts)

    def _get_avg_stop_pct(self, logs: dict[str, float]) -> float:
        custom = float(logs.get("custom/avg_stop_pct", 0.0))
        if custom > 0.0:
            return round(custom, 4)
        return compute_avg_pct(self._rolling.stop_pcts, default=0.008)

    def _get_avg_target_pct(self, logs: dict[str, float]) -> float:
        custom = float(logs.get("custom/avg_target_pct", 0.0))
        if custom > 0.0:
            return round(custom, 4)
        return compute_avg_pct(self._rolling.target_pcts, default=0.019)
