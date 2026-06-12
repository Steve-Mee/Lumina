"""OOS certificate evaluation for Birth Phase v2."""

from __future__ import annotations

import math
from typing import Any

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.sim_runner import run_policy_rollout


def _sharpe_from_pnl(pnl_series: list[float]) -> float:
    if len(pnl_series) < 5:
        return 0.0
    mean = sum(pnl_series) / len(pnl_series)
    var = sum((x - mean) ** 2 for x in pnl_series) / max(1, len(pnl_series) - 1)
    std = math.sqrt(max(var, 1e-12))
    return float((mean / std) * math.sqrt(252.0))


def _max_drawdown_pct(pnl_series: list[float], *, equity: float = 50_000.0) -> float:
    curve = [equity]
    for pnl in pnl_series:
        curve.append(curve[-1] + pnl)
    peak = max(curve)
    if peak <= 0:
        return 100.0
    return max(0.0, (peak - curve[-1]) / peak * 100.0)


def evaluate_holdout_certificate(
    *,
    runtime: Any,
    holdout_data: list[dict[str, Any]],
    policy: Any,
    real_data_pct: float,
    holdout_days: int,
    constitution_violations: int,
    workspace_root: Any,
    thresholds: BirthCertificateThresholds,
    max_trades: int = 2000,
) -> dict[str, Any]:
    guard = BirthConstitutionGuard()
    rollout = run_policy_rollout(
        runtime=runtime,
        data=holdout_data,
        policy=policy,
        target_trades=max_trades,
        workspace_root=workspace_root,
        constitution_guard=guard,
    )
    total_violations = int(constitution_violations) + int(rollout.constitution_violations)
    winrate = float(rollout.wins) / float(max(1, rollout.trades))
    sharpe = _sharpe_from_pnl(rollout.pnl_series)
    drawdown = _max_drawdown_pct(rollout.pnl_series)
    regimes = sorted(set(rollout.regimes_seen))

    result = {
        "real_data_pct": float(real_data_pct),
        "oos_winrate": round(winrate, 4),
        "oos_sharpe": round(sharpe, 4),
        "oos_max_drawdown_pct": round(drawdown, 4),
        "constitution_violations": total_violations,
        "regimes_covered": regimes[: max(3, len(regimes))],
        "holdout_days": int(holdout_days),
        "holdout_trades": rollout.trades,
    }

    passed = True
    if total_violations != 0:
        passed = False
    if real_data_pct < thresholds.min_real_data_pct:
        passed = False
    if winrate < thresholds.min_oos_winrate:
        passed = False
    if sharpe < thresholds.min_oos_sharpe:
        passed = False
    if drawdown > thresholds.max_oos_drawdown_pct:
        passed = False
    if len(set(regimes)) < thresholds.min_regimes:
        passed = False
    if rollout.trades < thresholds.min_holdout_trades:
        passed = False

    result["certificate_passed"] = passed
    return result
