"""Dream Engine – thousands of fast what-if paths before DNA mutation.

Lightweight forward roll of equity shocks around the nightly report to surface
tail drawdowns and emit compact rule hints for evolution / logging.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from lumina_core.config_loader import ConfigLoader


@dataclass(slots=True)
class DreamReport:
    dream_count: int
    breach_count: int
    breach_rate: float
    worst_dd_ratio: float
    median_terminal_equity_delta: float
    rule_hints: tuple[str, ...]


def dream_engine_config() -> tuple[bool, int, int, float]:
    """Returns enabled, dream_count, horizon_days, drawdown_limit_ratio."""
    evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
    de = evolution_cfg.get("dream_engine", {}) if isinstance(evolution_cfg, dict) else {}
    if not isinstance(de, dict):
        return True, 4000, 7, 0.02
    enabled = bool(de.get("enabled", True))
    try:
        n = int(de.get("dream_count", 4000) or 4000)
    except (TypeError, ValueError):
        n = 4000
    n = max(200, min(50_000, n))
    try:
        h = int(de.get("horizon_days", 7) or 7)
    except (TypeError, ValueError):
        h = 7
    h = max(1, min(60, h))
    try:
        ddr = float(de.get("drawdown_limit_ratio", 0.02) or 0.02)
    except (TypeError, ValueError):
        ddr = 0.02
    ddr = max(0.005, min(0.25, ddr))
    return enabled, n, h, ddr


def run_dream_batch(
    nightly_report: dict[str, Any],
    *,
    dream_count: int,
    horizon_days: int,
    seed: int,
    drawdown_limit_ratio: float = 0.02,
) -> DreamReport:
    """Run ``dream_count`` independent fast-forward equity paths (vector-free, CPU-cheap)."""
    rng = random.Random(seed)
    base_eq = max(1.0, float(nightly_report.get("account_equity", 50_000.0) or 50_000.0))
    base_dd = abs(float(nightly_report.get("max_drawdown", 0.0) or 0.0))
    base_pnl = float(nightly_report.get("net_pnl", 0.0) or 0.0)
    vol_scale = max(1.0, base_dd / max(1.0, base_eq * 0.5))

    breaches = 0
    worst_dd = 0.0
    terminal_deltas: list[float] = []

    n = max(1, int(dream_count))
    horizon = max(1, int(horizon_days))

    for _ in range(n):
        peak = base_eq
        equity = base_eq
        max_dd_ratio = 0.0
        for _d in range(horizon):
            noise = rng.gauss(0.0, 0.14 * vol_scale)
            daily_pnl = (base_pnl / float(horizon)) * (1.0 + noise) + rng.gauss(0.0, base_eq * 0.0012 * vol_scale)
            equity += float(daily_pnl)
            peak = max(peak, equity)
            dd_ratio = max(0.0, (peak - equity) / base_eq)
            max_dd_ratio = max(max_dd_ratio, dd_ratio)

        if max_dd_ratio > drawdown_limit_ratio:
            breaches += 1
        worst_dd = max(worst_dd, max_dd_ratio)
        terminal_deltas.append((equity - base_eq) / base_eq)

    terminal_deltas.sort()
    mid = len(terminal_deltas) // 2
    median_delta = float(terminal_deltas[mid]) if terminal_deltas else 0.0
    breach_rate = breaches / float(n)

    hints: list[str] = []
    if breach_rate > 0.12:
        hints.append("strengthen_drawdown_kill_in_whatif_tail")
    if breach_rate > 0.22:
        hints.append("widen_challenger_pool_under_dream_stress")
    if median_delta < -0.015:
        hints.append("bias_regime_gates_toward_defensive")
    if worst_dd > drawdown_limit_ratio * 1.8:
        hints.append("flash_drawdown_escape_and_size_cap")

    return DreamReport(
        dream_count=n,
        breach_count=breaches,
        breach_rate=float(breach_rate),
        worst_dd_ratio=float(worst_dd),
        median_terminal_equity_delta=float(median_delta),
        rule_hints=tuple(hints),
    )
