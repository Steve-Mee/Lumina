"""RL training-layer Gymnasium environment: model fills, shaping; ``training_reward`` in ``info`` (not broker PnL)."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.rl.observation_builder import OBSERVATION_DIM, build_observation_vector
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
    compute_legacy_reward,
    trend_features_from_tick,
    update_trade_stats,
)

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception as exc:  # pragma: no cover
    logging.exception("Unhandled broad exception fallback in lumina_core/rl/gym_environment.py")
    raise RuntimeError("gymnasium is required for RLTradingEnvironment") from exc


@dataclass(slots=True)
class RLConfig:
    """RL execution-cost and reward controls (training layer only — not broker economic PnL)."""

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
    reward: BirthRewardConfig = field(default_factory=BirthRewardConfig)


class RLTradingEnvironment(gym.Env):
    """Gymnasium-compatible training environment: Gym ``reward`` is a shaped training signal only."""

    metadata = {"render_modes": ["human"]}

    def __init__(self, engine, simulator_data: list[dict[str, Any]], config: RLConfig | None = None):
        super().__init__()
        self.engine = engine
        self.data = simulator_data
        self.config = config or self._config_from_engine(engine)
        self.valuation_engine = ValuationEngine()
        self.instrument = str(getattr(getattr(self.engine, "config", None), "instrument", "MES") or "MES")
        self.trade_mode = (
            str(self.config.trade_mode or getattr(getattr(self.engine, "config", None), "trade_mode", "sim"))
            .strip()
            .lower()
        )

        self.action_space = spaces.Box(
            low=np.array([0.0, 0.0, 0.001, 0.001], dtype=np.float32),
            high=np.array([2.0, 1.0, 0.02, 0.05], dtype=np.float32),
            dtype=np.float32,
        )

        self.observation_space = spaces.Box(
            low=-1e6,
            high=1e6,
            shape=(OBSERVATION_DIM,),
            dtype=np.float32,
        )

        self._dna_hash: str = ""
        self._birth_workspace_root: Any = None
        self._birth_constitution_guard: Any = None
        self._idx = 0
        self._position = 0
        self._qty = 0
        self._entry_price = 0.0
        self._equity = 50000.0
        self._initial_equity = 50000.0
        self._equity_curve: list[float] = [50000.0]
        self._returns: list[float] = []
        self._entry_stop_pct = 0.0075
        self._entry_side = 0
        self._reward_state = RewardShapingState()

    def _uses_expectancy_reward(self) -> bool:
        return self.trade_mode in {"birth", "sim"} and bool(self.config.reward.enabled)

    def _reward_cfg(self) -> BirthRewardConfig:
        return self.config.reward

    def set_dna_hash(self, dna_hash: str) -> None:
        """Inject active PolicyDNA hash so the policy can condition on lineage identity."""
        self._dna_hash = str(dna_hash or "")

    def set_birth_context(self, *, workspace_root: Any = None, constitution_guard: Any = None) -> None:
        self._birth_workspace_root = workspace_root
        self._birth_constitution_guard = constitution_guard

    def _dna_embedding(self) -> list[float]:
        from lumina_core.rl.observation_builder import dna_embedding

        return dna_embedding(self._dna_hash)

    @staticmethod
    def _config_from_engine(engine: Any) -> RLConfig:
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
        self._entry_stop_pct = 0.0075
        self._entry_side = 0
        self._reward_state = RewardShapingState()
        return self._get_observation(), {}

    def step(self, action):
        reward = 0.0
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
            if self.trade_mode == "birth" and self._birth_constitution_guard is not None:
                tick_row = self.data[min(self._idx, len(self.data) - 1)]
                allowed, _reason = self._birth_constitution_guard.check_entry(
                    tick=tick_row,
                    side=side,
                    stop_pct=stop_pct,
                    equity=self._equity,
                )
                if not allowed:
                    blocked_by_capital_preservation = True
                    block_reason = "birth_constitution_blocked"
                    reward -= 2.0
                    self._idx += 1
                    return self._get_observation(), reward, False, False, {
                        "blocked_by_birth_constitution": True,
                        "block_reason": block_reason,
                    }

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
                    self._entry_stop_pct = stop_pct
                    self._entry_side = side
            else:
                self._position = side
                self._qty = qty
                self._entry_price = fill
                slippage_cost += entry_slippage_cost
                fees_cost += entry_fees
                self._entry_stop_pct = stop_pct
                self._entry_side = side

        trade_closed = False
        close_side = 0
        close_stop_pct = self._entry_stop_pct
        if self._position != 0:
            stop = self._entry_price * (1.0 - stop_pct if self._position > 0 else 1.0 + stop_pct)
            target = self._entry_price * (1.0 + target_pct if self._position > 0 else 1.0 - target_pct)

            hit_stop = (self._position > 0 and price <= stop) or (self._position < 0 and price >= stop)
            hit_target = (self._position > 0 and price >= target) or (self._position < 0 and price <= target)
            flatten = side == 0 and np.random.random() < 0.05

            if hit_stop or hit_target or flatten:
                close_side = self._entry_side
                close_stop_pct = self._entry_stop_pct
                trade_closed = True
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

        rl_close_accounting_net_usd = float(realized_pnl - slippage_cost - fees_cost)
        reward_components: dict[str, float] = {}

        if self._uses_expectancy_reward():
            if trade_closed:
                trend_strength, atr_norm = trend_features_from_tick(row)
                self._reward_state.drawdown = self._drawdown()
                self._reward_state.sharpe = self._rolling_sharpe()
                ctx = TradeCloseContext(
                    net_pnl=rl_close_accounting_net_usd,
                    equity=prev_equity,
                    stop_pct=close_stop_pct,
                    side=close_side,
                    trend_regime_strength=trend_strength,
                    trend_atr_norm=atr_norm,
                    var_es_penalty=var_es_penalty,
                )
                reward, reward_components = compute_expectancy_reward(
                    ctx,
                    self._reward_state,
                    self._reward_cfg(),
                )
                update_trade_stats(
                    self._reward_state,
                    rl_close_accounting_net_usd,
                    window=self._reward_cfg().rolling_trade_window,
                )
            else:
                reward = -var_es_penalty if var_es_penalty > 0 else 0.0
        else:
            reward_cfg = self._reward_cfg()
            reward = compute_legacy_reward(
                net_pnl=rl_close_accounting_net_usd,
                drawdown=self._drawdown(),
                sharpe=self._rolling_sharpe(),
                drawdown_penalty_coeff=reward_cfg.drawdown_penalty_coeff,
                sharpe_bonus_coeff=reward_cfg.sharpe_bonus_coeff,
                var_es_penalty=var_es_penalty,
            )

        if blocked_by_capital_preservation:
            reward -= 5.0

        self._idx += 1
        terminated = self._idx >= min(len(self.data) - 1, self.config.max_steps)

        training_reward = float(reward)
        info = {
            "model_close_gross_pnl_usd": realized_pnl,
            "rl_close_accounting_net_usd": rl_close_accounting_net_usd,
            "training_reward": training_reward,
            "slippage_cost": slippage_cost,
            "fees_cost": fees_cost,
            "equity": self._equity,
            "drawdown": self._drawdown(),
            "sharpe": self._rolling_sharpe(),
            "var_es_penalty": var_es_penalty,
            "reward_components": reward_components,
            "trade_closed": trade_closed,
            "blocked_by_capital_preservation": blocked_by_capital_preservation,
            "block_reason": block_reason,
        }
        return self._get_observation(), reward, terminated, False, info

    def _get_observation(self) -> np.ndarray:
        row = self.data[min(self._idx, len(self.data) - 1)]
        return build_observation_vector(
            row=row,
            engine=self.engine,
            data=self.data,
            idx=self._idx,
            position=self._position,
            qty=self._qty,
            entry_price=self._entry_price,
            equity=self._equity,
            drawdown=self._drawdown(),
            rolling_sharpe=self._rolling_sharpe(),
            dna_hash=self._dna_hash,
            trade_mode=self.trade_mode,
        )

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
