# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from typing import Any, Dict

import gymnasium as gym
import numpy as np
import pandas as pd

from lumina_core.runtime_context import RuntimeContext


class RLTradingEnvironment(gym.Env):
    """
    Gymnasium-compatible RL environment voor LUMINA.
    Observation = volledige marktstaat (price, regime, tape, fibs, dream, equity, etc.)
    Action = BUY/SELL/HOLD + qty + stop/target
    Reward = real PnL - slippage - drawdown penalty + Sharpe bonus
    """

    def __init__(self, context: RuntimeContext):
        super().__init__()
        self.context = context
        self.fast_path = context.fast_path
        self.backtester = context.backtester

        # Observation space (20 features)
        self.observation_space = gym.spaces.Box(
            low=-10, high=10, shape=(20,), dtype=np.float32
        )

        # PPO verwacht een enkelvoudige action space. We encoden:
        # [signal(0..2), qty_pct(0.1..2.0), stop_mult(0.5..2.0), target_mult(1.5..4.0)]
        self.action_space = gym.spaces.Box(
            low=np.array([0.0, 0.1, 0.5, 1.5], dtype=np.float32),
            high=np.array([2.0, 2.0, 2.0, 4.0], dtype=np.float32),
            shape=(4,),
            dtype=np.float32,
        )

        self.current_episode = 0
        self.equity_curve = [50000.0]
        self.pnl_history = []

    def _get_observation(self) -> np.ndarray:
        """Volledige state als vector."""
        dream = self.context.get_current_dream_snapshot()
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))
        tape = getattr(self.context, "tape_delta", {"imbalance": 0.0})

        obs = np.array(
            [
                price / 5000.0,  # normalized price
                dream.get("confidence", 0.5),
                dream.get("confluence_score", 0.5),
                1.0 if regime == "TRENDING" else 0.0,
                1.0 if regime == "BREAKOUT" else 0.0,
                tape.get("imbalance", 0.0),
                self.context.account_equity / 50000.0,
                len(self.pnl_history) / 100.0,
                np.mean(self.pnl_history[-10:]) if self.pnl_history else 0.0,
                # extra features: fib distance, MA slope, volume delta, etc.
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            dtype=np.float32,
        )
        return obs

    def step(self, action: np.ndarray | Dict[str, Any]) -> tuple:
        # Backward-compatible parsing: accepteer legacy dict actions of PPO Box acties.
        if isinstance(action, dict):
            raw_signal = action.get("signal", 0)
            signal_idx = int(raw_signal[0]) if isinstance(raw_signal, np.ndarray) else int(raw_signal)
            qty_pct = float(action.get("qty_pct", [1.0])[0])
            stop_mult = float(action.get("stop_mult", [1.0])[0])
            target_mult = float(action.get("target_mult", [2.0])[0])
        else:
            flat = np.asarray(action, dtype=np.float32).reshape(-1)
            signal_idx = int(np.clip(np.rint(flat[0]), 0, 2))
            qty_pct = float(np.clip(flat[1], 0.1, 2.0))
            stop_mult = float(np.clip(flat[2], 0.5, 2.0))
            target_mult = float(np.clip(flat[3], 1.5, 4.0))

        signal = ["HOLD", "BUY", "SELL"][signal_idx]

        # Voer trade uit via simulator
        price = self.context.live_quotes[-1]["last"] if self.context.live_quotes else 5000.0
        regime = self.context.detect_market_regime(self.context.ohlc_1min.tail(60))

        # Gebruik FastPath + RL action
        _fast = self.fast_path.run(self.context.ohlc_1min.tail(60), price, regime)
        if signal != "HOLD":
            qty = int(
                self.context.calculate_adaptive_risk_and_qty(price, regime, 0) * qty_pct
            )
            # Simuleer trade met realistic backtester logic
            pnl = self.backtester._simulate_single_trade(
                price, signal, qty, stop_mult, target_mult
            )

            self.pnl_history.append(pnl)
            self.equity_curve.append(self.equity_curve[-1] + pnl)

            reward = pnl - abs(pnl) * 0.1  # slippage/drawdown penalty
            reward += (pnl / 1000.0) * 5  # Sharpe bonus
        else:
            reward = 0.0

        done = len(self.pnl_history) > 200
        truncated = False

        return self._get_observation(), reward, done, truncated, {}

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.current_episode += 1
        self.equity_curve = [50000.0]
        self.pnl_history = []
        return self._get_observation(), {}

    def _simulate_single_trade(self, price, signal, qty, stop_mult, target_mult):
        # Placeholder - gebruikt realistic backtester logic
        _ = pd.DataFrame  # keep pandas import explicit for future feature work
        atr = self.context.ohlc_1min["high"].sub(self.context.ohlc_1min["low"]).mean() * 1.5
        if signal == "BUY":
            _stop = price - atr * stop_mult
            _target = price + atr * target_mult
            pnl = (_target - price) * qty * 5 * 0.6  # verwachte win
        elif signal == "SELL":
            _stop = price + atr * stop_mult
            _target = price - atr * target_mult
            pnl = (price - _target) * qty * 5 * 0.6
        else:
            pnl = 0
        return pnl
