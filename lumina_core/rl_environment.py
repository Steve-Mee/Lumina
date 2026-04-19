from __future__ import annotations
# pyright: reportMissingImports=false

from dataclasses import dataclass
import hashlib
import random
from typing import Any

import numpy as np
from lumina_core.engine.valuation_engine import ValuationEngine

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception as exc:  # pragma: no cover
    raise RuntimeError("gymnasium is required for RLTradingEnvironment") from exc


@dataclass(slots=True)
class RLConfig:
    """LIVING ORGANISM v51: RL execution-cost and reward controls."""

    max_steps: int = 5000
    slippage_points: float = 0.125
    slippage_sigma: float = 0.5
    slippage_volatility_factor: float = 1.0
    commission_per_side_usd: float = 1.29
    exchange_fee_per_side_usd: float = 0.35
    clearing_fee_per_side_usd: float = 0.10
    nfa_fee_per_side_usd: float = 0.02
    real_safety_threshold_usd: float = 1000.0
    real_safety_threshold_ratio: float = 0.90
    sim_var_penalty_coeff: float = 0.04
    sim_es_penalty_coeff: float = 0.06
    trade_mode: str = "sim"
    drawdown_penalty_coeff: float = 0.2
    sharpe_bonus_coeff: float = 0.05


class RLTradingEnvironment(gym.Env):
    """LIVING ORGANISM v51: Gymnasium-compatible environment with safety-first costs."""

    metadata = {"render_modes": ["human"]}

    def __init__(self, engine, simulator_data: list[dict[str, Any]], config: RLConfig | None = None):
        super().__init__()
        self.engine = engine
        self.data = simulator_data
        self.config = config or self._config_from_engine(engine)
        self.valuation_engine = ValuationEngine()
        self.instrument = str(getattr(self.engine.config, "instrument", "MES"))
        self.trade_mode = (
            str(self.config.trade_mode or getattr(getattr(self.engine, "config", None), "trade_mode", "sim"))
            .strip()
            .lower()
        )

        # Action layout: [side, qty_norm, stop_pct, target_pct]
        # side in [0, 2] -> HOLD, BUY, SELL
        self.action_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.001, 0.001], dtype=np.float32),
            high=np.array([2.0, 1.0, 0.02, 0.05], dtype=np.float32),
            dtype=np.float32,
        )

        # Observation includes price, regime, tape, dream, fib, world_model, and DNA-embedding features.
        # 24 market/account features + 4 DNA-hash embedding = 28 total (Meta-RL phase)
        self.observation_space = spaces.Box(
            low=-1e6,
            high=1e6,
            shape=(28,),
            dtype=np.float32,
        )

        self._dna_hash: str = ""
        self._idx = 0
        self._position = 0
        self._qty = 0
        self._entry_price = 0.0
        self._equity = 50000.0
        self._initial_equity = 50000.0
        self._equity_curve: list[float] = [50000.0]
        self._returns: list[float] = []

    def set_dna_hash(self, dna_hash: str) -> None:
        """Inject active PolicyDNA hash so the policy can condition on lineage identity."""
        self._dna_hash = str(dna_hash or "")

    def _dna_embedding(self) -> list[float]:
        """4-float DNA embedding: first 4 bytes of SHA-256(dna_hash), normalised to [-1, 1]."""
        if not self._dna_hash:
            return [0.0, 0.0, 0.0, 0.0]
        raw = hashlib.sha256(self._dna_hash.encode("utf-8")).digest()
        return [(b / 127.5) - 1.0 for b in raw[:4]]

    @staticmethod
    def _config_from_engine(engine: Any) -> RLConfig:
        """LIVING ORGANISM v51: Build RLConfig from runtime risk config with safe defaults."""
        risk_cfg = getattr(getattr(engine, "config", None), "risk_controller", {})
        risk_cfg = risk_cfg if isinstance(risk_cfg, dict) else {}
        trade_mode = str(getattr(getattr(engine, "config", None), "trade_mode", "sim") or "sim").strip().lower()
        return RLConfig(
            slippage_points=float(risk_cfg.get("slippage_base_points", 0.125) or 0.125),
            slippage_sigma=float(risk_cfg.get("slippage_sigma", 0.5) or 0.5),
            slippage_volatility_factor=float(risk_cfg.get("slippage_volatility_factor", 1.0) or 1.0),
            commission_per_side_usd=float(risk_cfg.get("commission_per_side_usd", 1.29) or 1.29),
            exchange_fee_per_side_usd=float(risk_cfg.get("exchange_fee_per_side_usd", 0.35) or 0.35),
            clearing_fee_per_side_usd=float(risk_cfg.get("clearing_fee_per_side_usd", 0.10) or 0.10),
            nfa_fee_per_side_usd=float(risk_cfg.get("nfa_fee_per_side_usd", 0.02) or 0.02),
            real_safety_threshold_usd=float(risk_cfg.get("real_capital_safety_threshold_usd", 1000.0) or 1000.0),
            real_safety_threshold_ratio=float(risk_cfg.get("real_capital_safety_threshold_ratio", 0.90) or 0.90),
            sim_var_penalty_coeff=float(risk_cfg.get("sim_var_penalty_coeff", 0.04) or 0.04),
            sim_es_penalty_coeff=float(risk_cfg.get("sim_es_penalty_coeff", 0.06) or 0.06),
            trade_mode=trade_mode,
        )

    def _recent_volatility_points(self, price: float) -> float:
        closes = [
            float(self.data[i].get("close", self.data[i].get("last", 0.0)) or 0.0)
            for i in range(max(0, self._idx - 30), self._idx + 1)
        ]
        closes = [c for c in closes if c > 0.0]
        if len(closes) < 6 or price <= 0.0:
            return max(self.valuation_engine.tick_size(self.instrument), self.config.slippage_points)
        arr = np.asarray(closes, dtype=np.float64)
        ret = np.diff(arr) / np.maximum(arr[:-1], 1e-9)
        vol = float(np.std(ret))
        return max(self.valuation_engine.tick_size(self.instrument), abs(vol * price))

    def _stochastic_slippage_points(self, price: float) -> float:
        """LIVING ORGANISM v51: stochastic slippage = base + volatility_factor * gauss(0, sigma)."""
        base = float(self.config.slippage_points)
        volatility_factor = float(self.config.slippage_volatility_factor) * self._recent_volatility_points(price)
        shock = random.gauss(0.0, float(self.config.slippage_sigma))
        return float(max(0.0, base + (volatility_factor * shock)))

    def _fees_usd(self, *, quantity: int, sides: int) -> float:
        per_side = (
            float(self.config.commission_per_side_usd)
            + float(self.config.exchange_fee_per_side_usd)
            + float(self.config.clearing_fee_per_side_usd)
            + float(self.config.nfa_fee_per_side_usd)
        )
        return float(max(0, int(quantity)) * max(1, int(sides)) * max(0.0, per_side))

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self._idx = 60
        self._position = 0
        self._qty = 0
        self._entry_price = 0.0
        self._equity = 50000.0
        self._initial_equity = 50000.0
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
        fees_cost = 0.0
        blocked_by_capital_preservation = False
        block_reason = ""

        if self._position == 0 and side != 0:
            slippage_points = self._stochastic_slippage_points(price)
            entry_ticks = max(0.0, float(slippage_points) / max(self.valuation_engine.tick_size(self.instrument), 1e-9))
            fill = self.valuation_engine.apply_entry_fill(
                symbol=self.instrument,
                price=price,
                side=side,
                slippage_ticks=entry_ticks,
            )
            entry_slippage_cost = abs(fill - price) * qty * self.valuation_engine.point_value(self.instrument)
            entry_fees = self._fees_usd(quantity=qty, sides=1)

            if self.trade_mode == "real":
                safety_floor = max(
                    float(self.config.real_safety_threshold_usd),
                    float(self._initial_equity * float(self.config.real_safety_threshold_ratio)),
                )
                projected_equity = float(self._equity - entry_slippage_cost - entry_fees)
                if projected_equity < safety_floor:
                    blocked_by_capital_preservation = True
                    block_reason = (
                        "REAL fail-closed: projected net below safety threshold "
                        f"({projected_equity:.2f} < {safety_floor:.2f})"
                    )
                else:
                    self._position = side
                    self._qty = qty
                    self._entry_price = fill
                    slippage_cost += entry_slippage_cost
                    fees_cost += entry_fees
            else:
                self._position = side
                self._qty = qty
                self._entry_price = fill
                slippage_cost += entry_slippage_cost
                fees_cost += entry_fees

        if self._position != 0:
            stop = self._entry_price * (1.0 - stop_pct if self._position > 0 else 1.0 + stop_pct)
            target = self._entry_price * (1.0 + target_pct if self._position > 0 else 1.0 - target_pct)

            hit_stop = (self._position > 0 and price <= stop) or (self._position < 0 and price >= stop)
            hit_target = (self._position > 0 and price >= target) or (self._position < 0 and price <= target)
            flatten = side == 0 and np.random.random() < 0.05

            if hit_stop or hit_target or flatten:
                exit_ticks = max(
                    0.0,
                    float(self._stochastic_slippage_points(price))
                    / max(self.valuation_engine.tick_size(self.instrument), 1e-9),
                )
                exit_fill = self.valuation_engine.apply_exit_fill(
                    symbol=self.instrument,
                    price=price,
                    side=self._position,
                    slippage_ticks=exit_ticks,
                )
                slippage_cost += abs(exit_fill - price) * self._qty * self.valuation_engine.point_value(self.instrument)
                fees_cost += self._fees_usd(quantity=self._qty, sides=1)
                realized_pnl = self.valuation_engine.pnl_dollars(
                    symbol=self.instrument,
                    entry_price=self._entry_price,
                    exit_price=exit_fill,
                    side=self._position,
                    quantity=self._qty,
                )
                self._position = 0
                self._qty = 0
                self._entry_price = 0.0

        prev_equity = self._equity
        self._equity += realized_pnl - slippage_cost - fees_cost
        self._equity_curve.append(self._equity)

        ret = (self._equity - prev_equity) / max(prev_equity, 1e-6)
        self._returns.append(ret)
        drawdown_penalty = self._drawdown() * self.config.drawdown_penalty_coeff
        sharpe_bonus = self._rolling_sharpe() * self.config.sharpe_bonus_coeff
        reward = float(realized_pnl - slippage_cost - fees_cost - drawdown_penalty + sharpe_bonus)

        var_es_penalty = 0.0
        risk_controller = getattr(self.engine, "risk_controller", None)
        if self.trade_mode == "sim" and risk_controller is not None and hasattr(risk_controller, "get_var_es_snapshot"):
            snapshot = risk_controller.get_var_es_snapshot(proposed_risk=0.0)
            limits = getattr(risk_controller, "_active_limits", None)
            var_limit = max(float(getattr(limits, "var_95_limit_usd", 1.0) or 1.0), 1.0)
            es_limit = max(float(getattr(limits, "es_95_limit_usd", 1.0) or 1.0), 1.0)
            var_ratio = float(snapshot.get("var_95_usd", 0.0) or 0.0) / var_limit
            es_ratio = float(snapshot.get("es_95_usd", 0.0) or 0.0) / es_limit
            var_es_penalty = float(self.config.sim_var_penalty_coeff) * max(0.0, var_ratio) + float(
                self.config.sim_es_penalty_coeff
            ) * max(0.0, es_ratio)
            reward -= var_es_penalty

        if blocked_by_capital_preservation:
            reward -= 5.0

        self._idx += 1
        terminated = self._idx >= min(len(self.data) - 1, self.config.max_steps)

        info = {
            "realized_pnl": realized_pnl,
            "slippage_cost": slippage_cost,
            "fees_cost": fees_cost,
            "equity": self._equity,
            "drawdown": self._drawdown(),
            "sharpe": self._rolling_sharpe(),
            "var_es_penalty": var_es_penalty,
            "blocked_by_capital_preservation": blocked_by_capital_preservation,
            "block_reason": block_reason,
        }
        return self._get_observation(), reward, terminated, False, info

    def _get_observation(self) -> np.ndarray:
        row = self.data[min(self._idx, len(self.data) - 1)]
        price = float(row.get("close", row.get("last", 0.0)))

        recent = self.data[max(0, self._idx - 120) : self._idx + 1]
        regime = (
            str(self.engine.detect_market_regime(__import__("pandas").DataFrame(recent)))
            if len(recent) > 20
            else "NEUTRAL"
        )
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
                # DNA embedding (Meta-RL: policy conditions on active lineage identity)
                *self._dna_embedding(),
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
