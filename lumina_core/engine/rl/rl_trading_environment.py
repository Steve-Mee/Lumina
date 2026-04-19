# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

import hashlib
from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.engine.valuation_engine import ValuationEngine
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
        self.valuation_engine = ValuationEngine()
        self.instrument = str(self.context.engine.config.instrument)
        self._dna_version = str(getattr(self.context.engine, "active_dna_version", "GENESIS") or "GENESIS")

        # Observation space (23 features: 9 market + 4 DNA-embedding + 10 reserved)
        self.observation_space = gym.spaces.Box(low=-10, high=10, shape=(23,), dtype=np.float32)

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

    def set_dna_version(self, dna_version: str) -> None:
        self._dna_version = str(dna_version)

    def _dna_embedding(self) -> list[float]:
        """4-float DNA embedding: first 4 bytes of SHA-256(dna_version), normalised to [-1, 1]."""
        digest = hashlib.sha256(self._dna_version.encode("utf-8")).digest()
        return [(b / 127.5) - 1.0 for b in digest[:4]]

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
                # DNA embedding (Meta-RL: 4-byte hash → policy conditions on lineage)
                *self._dna_embedding(),
                # reserved future features: fib distance, MA slope, volume delta, etc.
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

    def step(self, action: np.ndarray) -> tuple:
        flat = np.asarray(action, dtype=np.float32).reshape(-1)
        if flat.shape[0] != 4:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="RL_ACTION_SHAPE_INVALID",
                message=f"Expected action vector length 4, got {flat.shape[0]}.",
            )
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
            qty = int(self.context.calculate_adaptive_risk_and_qty(price, regime, 0) * qty_pct)
            pnl = self._simulate_single_trade(price, signal, qty, stop_mult, target_mult)

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
        _ = pd.DataFrame  # keep pandas import explicit for future feature work
        atr = self.context.ohlc_1min["high"].sub(self.context.ohlc_1min["low"]).mean() * 1.5

        side = 0
        if signal == "BUY":
            side = 1
            target_price = price + atr * target_mult
        elif signal == "SELL":
            side = -1
            target_price = price - atr * target_mult
        else:
            return 0.0

        slip_ticks = self.valuation_engine.slippage_ticks(
            volume=1.0,
            avg_volume=1.0,
            regime=str(self.context.detect_market_regime(self.context.ohlc_1min.tail(60))),
            slippage_scale=1.0,
        )
        entry_fill = self.valuation_engine.apply_entry_fill(
            symbol=self.instrument,
            price=float(price),
            side=side,
            slippage_ticks=slip_ticks,
        )
        exit_fill = self.valuation_engine.apply_exit_fill(
            symbol=self.instrument,
            price=float(target_price),
            side=side,
            slippage_ticks=slip_ticks,
        )

        gross = self.valuation_engine.pnl_dollars(
            symbol=self.instrument,
            entry_price=entry_fill,
            exit_price=exit_fill,
            side=side,
            quantity=int(qty),
        )
        fees = self.valuation_engine.commission_dollars(
            symbol=self.instrument,
            quantity=int(qty),
            sides=2,
        )
        return (gross - fees) * 0.6
