"""Stress-scenario suites for multi-reality SIM training.

Builds parallel ``nightly_report``-shaped payloads so :class:`MultiDaySimRunner`
can score DNA / weights under black-swan, flash-crash, regime-shift, and
liquidity stress without touching live order flow.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

# (name, pnl_mult, drawdown_mult, sharpe_mult) — drawdown_mult scales stress magnitude.
_STRESS_PRESETS: list[tuple[str, float, float, float]] = [
    ("baseline", 1.0, 1.0, 1.0),
    ("black_swan_1987_style", -2.8, 4.5, -1.4),
    ("flash_crash_2010_style", -2.2, 3.6, -1.0),
    ("covid_liquidity_gap", -1.9, 3.2, -0.85),
    ("regime_shift_bear", -1.1, 2.0, -0.55),
    ("regime_shift_chop", 0.25, 1.65, -0.22),
    ("liquidity_crash", -1.35, 2.75, -0.48),
    ("high_vol_squeeze", -0.55, 2.35, 0.08),
    ("gap_and_go_against", -1.6, 2.15, -0.62),
    ("trend_exhaustion_fade", 0.15, 1.55, -0.28),
    ("correlation_breakdown", -0.95, 2.25, -0.32),
    ("margin_spiral_stress", -1.15, 2.95, -0.38),
    ("microstructure_noise", 0.08, 1.7, -0.12),
    ("carry_unwind", -1.45, 2.5, -0.58),
    ("sovereign_shock_proxy", -1.25, 2.4, -0.45),
]


def _stable_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


def build_parallel_reports(
    base: dict[str, Any],
    count: int,
    *,
    seed: str = "lumina_multi_reality",
) -> list[dict[str, Any]]:
    """Return ``count`` stressed copies of ``base`` for parallel universe SIM.

    Cycles through historical / synthetic stress presets and adds a tiny
    deterministic jitter so seeds diverge even when presets repeat.
    """
    n = max(1, int(count))
    out: list[dict[str, Any]] = []
    base_eq = max(1.0, float(base.get("account_equity", 50_000.0) or 50_000.0))

    for i in range(n):
        name, pm, dm, sm = _STRESS_PRESETS[i % len(_STRESS_PRESETS)]
        rng = random.Random(_stable_int(f"{seed}|{name}|{i}"))
        jitter = 1.0 + rng.uniform(-0.02, 0.02)

        report = dict(base)
        pnl = float(base.get("net_pnl", 0.0) or 0.0) * pm * jitter
        dd = abs(float(base.get("max_drawdown", 0.0) or 0.0)) * dm * jitter
        sharpe = float(base.get("sharpe", 0.0) or 0.0) * sm * jitter

        report["net_pnl"] = pnl
        report["max_drawdown"] = dd
        report["sharpe"] = sharpe
        report.setdefault("account_equity", base_eq * (1.0 + rng.uniform(-0.01, 0.01)))

        report["_reality_id"] = i
        report["_reality_name"] = name
        out.append(report)

    return out
