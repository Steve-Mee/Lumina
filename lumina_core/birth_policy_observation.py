"""43-dim observation vectors via observation_builder SSOT (ADR-0015 + ADR-0018)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np

from lumina_core.rl.observation_builder import OBSERVATION_DIM, build_observation_vector

BIRTH_RL_OBS_DIM = OBSERVATION_DIM


def _position_side_scalar(side: str) -> float:
    normalized = str(side or "NONE").strip().upper()
    if normalized == "BUY":
        return 1.0
    if normalized == "SELL":
        return -1.0
    return 0.0


def _rolling_sharpe_from_pnl(recent_pnl: list[float]) -> float:
    if len(recent_pnl) < 5:
        return 0.0
    arr = np.asarray(recent_pnl[-100:], dtype=np.float32)
    std = float(arr.std())
    if std <= 1e-8:
        return 0.0
    return float((arr.mean() / std) * np.sqrt(252.0))


def _drawdown_from_pnl(recent_pnl: list[float], *, equity: float) -> float:
    if not recent_pnl:
        return 0.0
    curve = [float(equity)]
    for pnl in recent_pnl[-200:]:
        curve.append(curve[-1] + float(pnl))
    peak = max(curve) if curve else equity
    if peak <= 0.0:
        return 0.0
    return max(0.0, (peak - curve[-1]) / peak)


def build_birth_rl_observation_vector(
    *,
    tick: dict[str, Any],
    position: dict[str, Any] | None,
    tick_index: int,
    tick_count: int,
    equity: float = 50_000.0,
    recent_pnl: list[float] | None = None,
) -> np.ndarray:
    """Build observation compatible with ``RLTradingEnvironment.observation_space`` (43,)."""
    row = dict(tick)
    if "close" not in row and "last" in row:
        row["close"] = row["last"]

    pnl_tail = list(recent_pnl or [])
    pos_side = 0.0
    pos_qty = 0
    entry_price = 0.0
    if position is not None:
        pos_side = _position_side_scalar(str(position.get("side", "NONE")))
        pos_qty = max(0, int(position.get("qty", 1) or 1))
        entry_price = float(position.get("entry_price", 0.0) or 0.0)
        row.setdefault("stop", float(position.get("stop", row.get("last", 0.0)) or 0.0))
        row.setdefault("target", float(position.get("target", row.get("last", 0.0)) or 0.0))

    volume = float(tick.get("volume", 1) or 1)
    imbalance = float(tick.get("imbalance", 1.0) or 1.0)
    engine = SimpleNamespace(
        detect_market_regime=lambda _df: str(row.get("regime", "NEUTRAL")),
        market_data=SimpleNamespace(
            get_tape_snapshot=lambda: {
                "volume_delta": volume * imbalance * 0.01,
                "avg_volume_delta_10": volume * 0.01,
                "bid_ask_imbalance": imbalance,
                "cumulative_delta_10": imbalance * volume * 0.001,
            }
        ),
        get_current_dream_snapshot=lambda: {},
        AI_DRAWN_FIBS={},
        world_model={},
    )

    data = [row]
    return build_observation_vector(
        row=row,
        engine=engine,
        data=data,
        idx=max(0, int(tick_index)),
        position=pos_side,
        qty=pos_qty,
        entry_price=entry_price,
        equity=float(equity),
        drawdown=_drawdown_from_pnl(pnl_tail, equity=equity),
        rolling_sharpe=_rolling_sharpe_from_pnl(pnl_tail),
    )
