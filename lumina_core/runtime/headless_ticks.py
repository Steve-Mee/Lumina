# Headless tick resolution + fast-path simulation kernel.
from __future__ import annotations

import logging
import math
import os
import random
import statistics
from typing import Any

from lumina_core.evolution.simulator_data_support import (
    MIN_SIMULATOR_BARS,
    validate_simulator_bars,
)
from lumina_core.runtime.headless_config import (
    _resolve_headless_historical_days_back,
    _resolve_headless_historical_limit,
)

logger = logging.getLogger("lumina.headless")


def _require_real_simulator_data_strict() -> bool:
    # Prefer headless_runtime binding so tests can monkeypatch that module attr.
    import lumina_core.runtime.headless_runtime as hr

    fn = getattr(hr, "require_real_simulator_data_strict", None)
    if callable(fn):
        return bool(fn())
    from lumina_core.evolution.simulator_data_support import require_real_simulator_data_strict as _fn

    return bool(_fn())


def _get_market_data_service(container: Any | None) -> Any | None:
    if container is None:
        return None
    mds = getattr(container, "market_data_service", None)
    if mds is not None:
        return mds
    eng = getattr(container, "engine", None)
    if eng is not None:
        return getattr(eng, "market_data_service", None)
    return None


def _normalize_tick_for_headless(tick: dict[str, Any]) -> dict[str, Any]:
    last = float(tick.get("last") or tick.get("close") or 0.0)
    vol = float(tick.get("volume") or 0.0)
    out = dict(tick)
    out["last"] = last
    out["volume"] = vol
    out.setdefault("regime", "NEUTRAL")
    out.setdefault("imbalance", 1.0)
    return out


def _build_headless_ticks_from_history(
    raw: list[dict[str, Any]],
    n_target: int,
    seed: int,
) -> list[dict[str, Any]]:
    if n_target <= 0:
        return []
    rng = random.Random(seed)
    if len(raw) >= n_target:
        start = rng.randint(0, len(raw) - n_target)
        window = raw[start : start + n_target]
    else:
        window: list[dict[str, Any]] = []
        while len(window) < n_target:
            window.extend(raw)
        window = window[:n_target]
    return [_normalize_tick_for_headless(t) for t in window]


def _resolve_headless_ticks(
    *,
    n_ticks: int,
    seed: int,
    container: Any | None,
    headless_cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], str]:
    """Return (ticks, source) where source is ``historical`` or ``synthetic``."""
    if _require_real_simulator_data_strict():
        mds = _get_market_data_service(container)
        if mds is None or not hasattr(mds, "load_historical_ohlc_extended"):
            fallback = os.getenv("LUMINA_HEADLESS_FALLBACK_SYNTHETIC", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
            if fallback:
                logger.warning(
                    "require_real_simulator_data is true but historical OHLC service is unavailable; "
                    "LUMINA_HEADLESS_FALLBACK_SYNTHETIC is set — using synthetic ticks for this headless run."
                )
                return _generate_synthetic_ticks(n=n_ticks, seed=seed), "synthetic"
            raise RuntimeError(
                "headless historical mode (evolution.neuroevolution.require_real_simulator_data=true) needs "
                "MarketDataService.load_historical_ohlc_extended (Crosstrade historical API). "
                "Fix: set require_real_simulator_data to false in config.yaml for synthetic headless ticks; "
                "or set CROSSTRADE_TOKEN + broker so the runtime container can fetch history; "
                "or export LUMINA_HEADLESS_FALLBACK_SYNTHETIC=1 for one-off synthetic fallback (logs a warning)."
            )
        days_back = _resolve_headless_historical_days_back(headless_cfg)
        limit = _resolve_headless_historical_limit(headless_cfg)
        raw = mds.load_historical_ohlc_extended(days_back=days_back, limit=limit, ticks_per_bar=4)
        if not isinstance(raw, list) or len(raw) < MIN_SIMULATOR_BARS:
            raise RuntimeError(
                f"headless historical fetch returned insufficient ticks "
                f"({len(raw) if isinstance(raw, list) else 0}); check API credentials and fetch limits."
            )
        ok, code = validate_simulator_bars(raw)
        if not ok:
            raise RuntimeError(f"headless historical ticks failed validation: {code}")
        return _build_headless_ticks_from_history(raw, n_target=n_ticks, seed=seed), "historical"

    return _generate_synthetic_ticks(n=n_ticks, seed=seed), "synthetic"


def _empty_sim_metrics() -> dict[str, Any]:
    return {
        "total_trades": 0,
        "pnl_realized": 0.0,
        "max_drawdown": 0.0,
        "risk_events": 0,
        "var_breach_count": 0,
        "wins": 0,
        "win_rate": 0.0,
        "mean_pnl_per_trade": 0.0,
        "sharpe_annualized": 0.0,
    }


def _generate_synthetic_ticks(n: int, seed: int, start_price: float = 5000.0) -> list[dict[str, Any]]:
    """Generate n synthetic price ticks for a rapid paper simulation."""
    rng = random.Random(seed)
    regimes = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "NEUTRAL"]
    ticks: list[dict[str, Any]] = []
    price = start_price
    regime_idx = 0
    regime_ticks = 0
    regime_dur = rng.randint(40, 120)

    for _ in range(n):
        regime_ticks += 1
        if regime_ticks >= regime_dur:
            regime_idx = (regime_idx + 1) % len(regimes)
            regime_dur = rng.randint(40, 120)
            regime_ticks = 0

        regime = regimes[regime_idx]
        drift = 0.12 if regime == "TRENDING_UP" else (-0.12 if regime == "TRENDING_DOWN" else 0.0)
        price += drift + rng.gauss(0, 0.4)
        price = max(100.0, price)

        ticks.append(
            {
                "last": round(price, 2),
                "volume": rng.uniform(80, 1200),
                "regime": regime,
                "imbalance": rng.uniform(0.5, 2.0),
            }
        )
    return ticks


def _run_simulation(
    ticks: list[dict[str, Any]],
    seed: int,
    mode: str = "paper",
    apply_learning_shaping: bool | None = None,
    symbol: str = "MES",
    point_value: float = 5.0,
    commission_per_side: float = 2.55,
) -> dict[str, Any]:
    """
    Core simulation loop.  Processes ticks and returns trade statistics.
    Deliberately fast (pure Python, sub-second for <=50 k ticks).
    """
    rng = random.Random(seed)
    pnl_values: list[float] = []
    running_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0
    risk_events = 0
    var_events = 0
    var_limit_usd = 1200.0
    if apply_learning_shaping is None:
        is_sim_learning = str(mode).strip().lower() == "sim"
    else:
        is_sim_learning = bool(apply_learning_shaping)
    daily_loss_cap = -1_000_000.0 if is_sim_learning else -1000.0

    position = 0
    qty = 1
    entry = 0.0
    stop = 0.0
    target = 0.0
    hold_ticks = 0

    for tick in ticks:
        price = float(tick["last"])
        regime = str(tick["regime"])
        imbalance = float(tick["imbalance"])

        if position == 0:
            entry_prob = 0.22 if "TREND" in regime else 0.14
            if rng.random() < entry_prob:
                side = 1 if (imbalance >= 1.0 and rng.random() < 0.55) else -1
                if "RANGING" in regime and rng.random() < 0.6:
                    side *= -1
                position = side
                # SIM learning mode allows larger sizing for aggressive exploration.
                qty = rng.randint(2, 8) if is_sim_learning else rng.randint(1, 3)
                entry = price
                sl_dist = 0.25 * rng.uniform(0.6, 1.4)
                tp_dist = 0.25 * rng.uniform(1.2, 3.0)
                stop = entry - sl_dist * position
                target = entry + tp_dist * position
                hold_ticks = 0
            continue

        hold_ticks += 1
        stop_hit = (position > 0 and price <= stop) or (position < 0 and price >= stop)
        target_hit = (position > 0 and price >= target) or (position < 0 and price <= target)
        timed_exit = hold_ticks >= 24

        if stop_hit or target_hit or timed_exit:
            gross = (price - entry) * position * qty * point_value
            net = gross - commission_per_side * 2.0 * qty

            if is_sim_learning:
                # SIM learning profile: reward exploratory winners more and soften
                # losing outcomes to keep the evolutionary loop productive.
                if gross >= 0:
                    net = (gross * 1.55) - (commission_per_side * qty * 0.5)
                else:
                    net = (gross * 0.35) - (commission_per_side * qty * 0.5)

            pnl_values.append(net)
            running_pnl += net

            if running_pnl > peak_pnl:
                peak_pnl = running_pnl
            drawdown = peak_pnl - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

            # Risk event tracking is disabled in SIM learning mode (unlimited budget).
            if (not is_sim_learning) and net < abs(daily_loss_cap) * 0.10 * -1:
                risk_events += 1

            # VaR-proxy breach enforced only in non-SIM mode.
            open_risk = abs(entry - stop) * qty * point_value
            if (not is_sim_learning) and open_risk > var_limit_usd * 0.80:
                var_events += 1

            position = 0
            qty = 1
            hold_ticks = 0

    total = len(pnl_values)
    net_pnl = float(sum(pnl_values)) if pnl_values else 0.0
    wins = sum(1 for p in pnl_values if p > 0)
    mean_pnl = float(statistics.mean(pnl_values)) if pnl_values else 0.0
    std_pnl = float(statistics.pstdev(pnl_values)) if len(pnl_values) > 1 else 0.0
    sharpe = (mean_pnl / std_pnl) * math.sqrt(252.0) if std_pnl > 1e-9 else 0.0

    return {
        "total_trades": total,
        "pnl_realized": round(net_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "risk_events": risk_events,
        "var_breach_count": var_events,
        "wins": wins,
        "win_rate": round(wins / total, 4) if total > 0 else 0.0,
        "mean_pnl_per_trade": round(mean_pnl, 2),
        "sharpe_annualized": round(sharpe, 4),
    }


# ---------------------------------------------------------------------------
# Broker validation helper
# ---------------------------------------------------------------------------


