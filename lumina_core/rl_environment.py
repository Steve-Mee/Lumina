from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass
from typing import Any

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception as exc:  # pragma: no cover
    raise RuntimeError("gymnasium is required for RLTradingEnvironment") from exc


@dataclass(slots=True)
class RLConfig:
    max_steps: int = 5000
    slippage_points: float = 0.125
    drawdown_penalty_coeff: float = 0.2
    sharpe_bonus_coeff: float = 0.05


class RLTradingEnvironment(gym.Env):
    """Gymnasium-compatible environment backed by LuminaEngine state."""

    metadata = {"render_modes": ["human"]}

    def __init__(self, engine, simulator_data: list[dict[str, Any]], config: RLConfig | None = None):
        super().__init__()
        self.engine = engine
        self.data = simulator_data
        self.config = config or RLConfig()

        # Action layout: [side, qty_norm, stop_pct, target_pct]
        # side in [0, 2] -> HOLD, BUY, SELL
        self.action_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.001, 0.001], dtype=np.float32),
            high=np.array([2.0, 1.0, 0.02, 0.05], dtype=np.float32),
            dtype=np.float32,
        )

        # Observation includes price, regime, tape, dream, fib, and world_model features.
        self.observation_space = spaces.Box(
            low=-1e6,
            high=1e6,
            shape=(24,),
            dtype=np.float32,
        )

        self._idx = 0
        self._position = 0
        self._qty = 0
        self._entry_price = 0.0
        self._equity = 50000.0
        self._equity_curve: list[float] = [50000.0]
        self._returns: list[float] = []

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._idx = 60
        self._position = 0
        self._qty = 0
        self._entry_price = 0.0
        self._equity = 50000.0
        self._equity_curve = [50000.0]
        self._returns = []
        return self._get_observation(), {}

    def step(self, action):
        action_arr = np.asarray(action, dtype=np.float32)
        if self._idx >= len(self.data) - 1:
            return self._get_observation(), 0.0, True, False, {}

        row = self.data[self._idx]
        price = float(row.get("close", row.get("last", 0.0)))
        if price <= 0.0:
            self._idx += 1
            return self._get_observation(), -0.01, False, False, {"skip": "invalid_price"}

        side_bucket = int(np.clip(np.round(action_arr[0]), 0, 2))
        side = 0 if side_bucket == 0 else (1 if side_bucket == 1 else -1)
        qty = max(1, int(1 + np.clip(action_arr[1], 0.0, 1.0) * 9))
        stop_pct = float(np.clip(action_arr[2], 0.001, 0.02))
        target_pct = float(np.clip(action_arr[3], 0.001, 0.05))

        realized_pnl = 0.0
        slippage_cost = 0.0

        if self._position == 0 and side != 0:
            self._position = side
            self._qty = qty
            fill = price + (self.config.slippage_points * side)
            self._entry_price = fill
            slippage_cost += abs(fill - price) * qty * 5.0

        if self._position != 0:
            stop = self._entry_price * (1.0 - stop_pct if self._position > 0 else 1.0 + stop_pct)
            target = self._entry_price * (1.0 + target_pct if self._position > 0 else 1.0 - target_pct)

            hit_stop = (self._position > 0 and price <= stop) or (self._position < 0 and price >= stop)
            hit_target = (self._position > 0 and price >= target) or (self._position < 0 and price <= target)
            flatten = side == 0 and np.random.random() < 0.05

            if hit_stop or hit_target or flatten:
                exit_fill = price - (self.config.slippage_points * self._position)
                slippage_cost += abs(exit_fill - price) * self._qty * 5.0
                realized_pnl = (exit_fill - self._entry_price) * self._position * self._qty * 5.0
                self._position = 0
                self._qty = 0
                self._entry_price = 0.0

        prev_equity = self._equity
        self._equity += realized_pnl - slippage_cost
        self._equity_curve.append(self._equity)

        ret = (self._equity - prev_equity) / max(prev_equity, 1e-6)
        self._returns.append(ret)
        drawdown_penalty = self._drawdown() * self.config.drawdown_penalty_coeff
        sharpe_bonus = self._rolling_sharpe() * self.config.sharpe_bonus_coeff
        reward = float(realized_pnl - slippage_cost - drawdown_penalty + sharpe_bonus)

        self._idx += 1
        terminated = self._idx >= min(len(self.data) - 1, self.config.max_steps)

        info = {
            "realized_pnl": realized_pnl,
            "slippage_cost": slippage_cost,
            "equity": self._equity,
            "drawdown": self._drawdown(),
            "sharpe": self._rolling_sharpe(),
        }
        return self._get_observation(), reward, terminated, False, info

    def _get_observation(self) -> np.ndarray:
        row = self.data[min(self._idx, len(self.data) - 1)]
        price = float(row.get("close", row.get("last", 0.0)))

        recent = self.data[max(0, self._idx - 120): self._idx + 1]
        regime = str(self.engine.detect_market_regime(__import__("pandas").DataFrame(recent))) if len(recent) > 20 else "NEUTRAL"
        regime_map = {
            "TRENDING": 1.0,
            "BREAKOUT": 0.8,
            "RANGING": -0.6,
            "VOLATILE": -0.9,
            "NEUTRAL": 0.0,
        }
        regime_val = 0.0
        for key, val in regime_map.items():
            if key in regime.upper():
                regime_val = val
                break

        tape = self.engine.market_data.get_tape_snapshot()
        dream = self.engine.get_current_dream_snapshot()
        fib_levels = dream.get("fib_levels") or self.engine.AI_DRAWN_FIBS or {}
        world_model = self.engine.world_model or {}
        macro = world_model.get("macro", {}) if isinstance(world_model, dict) else {}

        fib_0382 = float(fib_levels.get("0.382", price)) if isinstance(fib_levels, dict) else price
        fib_05 = float(fib_levels.get("0.5", price)) if isinstance(fib_levels, dict) else price
        fib_0618 = float(fib_levels.get("0.618", price)) if isinstance(fib_levels, dict) else price

        obs = np.array(
            [
                price,
                regime_val,
                float(tape.get("volume_delta", 0.0)),
                float(tape.get("avg_volume_delta_10", 0.0)),
                float(tape.get("bid_ask_imbalance", 1.0)),
                float(tape.get("cumulative_delta_10", 0.0)),
                float(dream.get("confidence", 0.0)),
                float(dream.get("confluence_score", 0.0)),
                float(dream.get("stop", 0.0)),
                float(dream.get("target", 0.0)),
                fib_0382,
                fib_05,
                fib_0618,
                float(macro.get("vix", 0.0)),
                float(macro.get("yield10y", 0.0)),
                float(macro.get("dxy", 0.0)),
                float(self._position),
                float(self._qty),
                float(self._entry_price),
                float(self._equity),
                float(self._drawdown()),
                float(self._rolling_sharpe()),
                float(self._idx),
                float(len(self.data)),
            ],
            dtype=np.float32,
        )
        return obs

    def _drawdown(self) -> float:
        peak = max(self._equity_curve) if self._equity_curve else self._equity
        if peak <= 0:
            return 0.0
        return max(0.0, (peak - self._equity) / peak)

    def _rolling_sharpe(self) -> float:
        if len(self._returns) < 5:
            return 0.0
        arr = np.array(self._returns[-100:], dtype=np.float32)
        std = float(arr.std())
        if std <= 1e-8:
            return 0.0
        return float((arr.mean() / std) * np.sqrt(252.0))

    def render(self):
        return None
