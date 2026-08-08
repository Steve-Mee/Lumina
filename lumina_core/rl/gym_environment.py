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
from lumina_core.rl.gym_environment_step import RLTradingEnvironmentStepMixin
from lumina_core.rl.reward_shaper import (
    RewardShapingState,
    TradeCloseContext,
    compute_expectancy_reward,
    compute_legacy_reward,
    hold_action_penalty,
    range_patience_step_reward,
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
    plateau_active: bool = False
    hold_penalty_coeff: float = 0.002
    range_patience_active: bool = False
    # Stage2 participation envelope: block random flatten while forcing dwell.
    suppress_random_flatten: bool = False
    # When >0 and suppress_random_flatten, skip stop/target exits until dwell.
    # Birth SIM occupancy law only — does not widen stops past constitution 1%.
    participation_min_dwell_bars: int = 0
    # Birth SIM: floor equity so risk checks / plant survival stay well-defined.
    birth_equity_floor_ratio: float = 0.10
    # Stage-2 quality stack: seed expectancy gap (floor − live) for range reward.
    expectancy_gap: float = 0.0
    stage2_expectancy_floor: float = -0.15


class RLTradingEnvironment(RLTradingEnvironmentStepMixin, gym.Env):
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
        self._entry_target_pct = 0.015
        self._entry_side = 0
        self._reward_state = RewardShapingState()
        # Rolling range-flat for Stage-2 band-aware reward shaping.
        self._range_flat_bars = 0
        self._range_total_bars = 0
        # Bars held in current position (envelope min-dwell occupancy protect).
        self._bars_held = 0

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
        self._entry_target_pct = 0.015
        self._entry_side = 0
        self._reward_state = RewardShapingState()
        self._range_flat_bars = 0
        self._range_total_bars = 0
        self._bars_held = 0
        return self._get_observation(), {}

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
