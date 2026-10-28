"""RL training defaults that must not import archived Birth-v1 experiments.

Birth-v1 gym curriculum lives in ``archive/birth-v1/``. Live RL keeps MES
point-value and reward coefficients here so the trading engine can train
without the archived package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MES_POINT_VALUE_USD = 5.0
MIN_STOP_PCT = 0.0004
SEGMENT_BREAK_KEY = "_segment_break"


@dataclass(slots=True)
class BirthRewardConfig:
    """Expectancy-oriented PPO training reward (sim/paper). Not a claimed edge."""

    enabled: bool = True
    expectancy_coeff: float = 0.5
    quality_win_bonus_coeff: float = 0.25
    loss_asymmetry_coeff: float = 1.25
    volatility_penalty_coeff: float = 0.15
    atr_floor: float = 0.0005
    trend_align_bonus_coeff: float = 0.10
    drawdown_penalty_coeff: float = 0.20
    sharpe_bonus_coeff: float = 0.05
    min_risk_usd: float = 25.0
    reward_clip: float = 5.0
    rolling_trade_window: int = 50
    range_flat_bonus_coeff: float = 0.003
    range_churn_penalty_coeff: float = 0.005
    range_quality_boost_coeff: float = 0.15
    s3_inband_hold_tax: float = 0.01
    s3_inband_min_idle_hold_bars: int = 32


def import_sb3_ppo() -> Any:
    """Import Stable-Baselines3 PPO or fail closed."""
    try:
        from stable_baselines3 import PPO
    except ModuleNotFoundError as exc:
        missing = str(exc.name or "stable_baselines3")
        raise RuntimeError(f"Leermotor ontbreekt ({missing}).") from exc
    return PPO


def require_sb3_base_callback() -> Any:
    try:
        from stable_baselines3.common.callbacks import BaseCallback
    except ImportError as exc:
        raise RuntimeError("Leermotor ontbreekt (stable_baselines3).") from exc
    return BaseCallback
