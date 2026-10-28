"""OOS certificate evaluation for Birth Phase v2."""

from __future__ import annotations

import math
from typing import Any

from lumina_core.birth.birth_constitution_guard import BirthConstitutionGuard
from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.data_source_honesty import real_data_percentage, synthetic_source_reasons
from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD
from lumina_core.birth.sim_runner import run_policy_rollout


def sharpe_from_pnl(pnl_series: list[float]) -> float:
    return _sharpe_from_pnl(pnl_series)


def max_drawdown_pct(pnl_series: list[float], *, equity: float = S5_DD_EQUITY_USD) -> float:
    return _max_drawdown_pct(pnl_series, equity=equity)


def _sharpe_from_pnl(pnl_series: list[float]) -> float:
    if len(pnl_series) < 5:
        return 0.0
    mean = sum(pnl_series) / len(pnl_series)
    var = sum((x - mean) ** 2 for x in pnl_series) / max(1, len(pnl_series) - 1)
    std = math.sqrt(max(var, 1e-12))
    return float((mean / std) * math.sqrt(252.0))


def _peak_to_end_drawdown_pct(
    pnl_series: list[float], *, equity: float = S5_DD_EQUITY_USD
) -> float:
    """Diagnostic only. Peak-to-END giveback — not the exam yardstick."""
    curve = [float(equity)]
    for pnl in pnl_series:
        curve.append(curve[-1] + float(pnl))
    peak = max(curve)
    if peak <= 0:
        return 100.0
    return max(0.0, (peak - curve[-1]) / peak * 100.0)


def _max_drawdown_pct(pnl_series: list[float], *, equity: float = S5_DD_EQUITY_USD) -> float:
    """Max peak-to-trough DD% on running equity. ``pnl`` increments must be USD."""
    running = float(equity)
    peak = running
    dd_pct = 0.0
    if peak <= 0:
        return 100.0
    for pnl in pnl_series:
        running += float(pnl)
        if running > peak:
            peak = running
        if peak <= 0:
            return 100.0
        dd_pct = max(dd_pct, (peak - running) / peak * 100.0)
    return max(0.0, dd_pct)


def build_oos_regime_breakdown(trajectories: list[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Per-regime trade counts / winrate from rollout trajectories."""
    buckets: dict[str, list[float]] = {}
    for row in trajectories:
        if not isinstance(row, dict):
            continue
        if "pnl" not in row:
            continue
        regime = str(row.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper() or "NEUTRAL"
        buckets.setdefault(regime, []).append(float(row.get("pnl", 0.0) or 0.0))
    out: dict[str, dict[str, float | int]] = {}
    for regime, pnls in sorted(buckets.items()):
        trades = len(pnls)
        wins = sum(1 for p in pnls if p > 0)
        out[regime] = {
            "trades": trades,
            "wins": wins,
            "winrate": round(float(wins) / float(max(1, trades)), 4),
        }
    return out


def build_certificate_failure_reasons(
    *,
    real_data_pct: float,
    winrate: float,
    sharpe: float,
    drawdown: float,
    regimes: list[str],
    holdout_trades: int,
    constitution_violations: int,
    thresholds: BirthCertificateThresholds,
    regime_breakdown: dict[str, dict[str, float | int]] | None = None,
    holdout_ticks: list[dict[str, Any]] | None = None,
) -> list[str]:
    reasons: list[str] = []
    honest_pct = (
        real_data_percentage(holdout_ticks) if holdout_ticks else float(real_data_pct)
    )
    reported_pct = honest_pct if holdout_ticks else float(real_data_pct)
    if constitution_violations != 0:
        reasons.append(f"constitution_violations:{constitution_violations}/0")
    if reported_pct < thresholds.min_real_data_pct:
        reasons.append(
            f"real_data_pct:{reported_pct:.2f}/{thresholds.min_real_data_pct:.2f}"
        )
    reasons.extend(synthetic_source_reasons(holdout_ticks))
    if winrate < thresholds.min_oos_winrate:
        reasons.append(f"oos_winrate:{winrate:.2f}/{thresholds.min_oos_winrate:.2f}")
    if sharpe < thresholds.min_oos_sharpe:
        reasons.append(f"oos_sharpe:{sharpe:.2f}/{thresholds.min_oos_sharpe:.2f}")
    if drawdown > thresholds.max_oos_drawdown_pct:
        reasons.append(
            f"oos_max_drawdown_pct:{drawdown:.2f}/{thresholds.max_oos_drawdown_pct:.2f}"
        )
    regime_count = len(set(regimes))
    if regime_count < thresholds.min_regimes:
        reasons.append(f"regimes_covered:{regime_count}/{thresholds.min_regimes}")
    if holdout_trades < thresholds.min_holdout_trades:
        reasons.append(f"holdout_trades:{holdout_trades}/{thresholds.min_holdout_trades}")
    # Starship B2: when trajectory evidence exists, claimed regimes need ≥1 trade each.
    if regime_breakdown is not None and regimes:
        has_evidence = any(
            int((row or {}).get("trades", 0) or 0) > 0 for row in regime_breakdown.values()
        )
        if has_evidence:
            for regime in set(regimes):
                row = regime_breakdown.get(str(regime).upper()) or regime_breakdown.get(
                    str(regime)
                )
                trades = int((row or {}).get("trades", 0) or 0)
                if trades <= 0:
                    reasons.append(f"oos_regime_empty:{regime}")
    return reasons


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
    try:
        from lumina_core.birth.birth_trade_geometry import calibrate_birth_stops

        cert_geo = calibrate_birth_stops(list(holdout_data or []), max_hold_bars=90)
    except Exception:
        cert_geo = None
    rollout = run_policy_rollout(
        runtime=runtime,
        data=holdout_data,
        policy=policy,
        target_trades=max_trades,
        workspace_root=workspace_root,
        constitution_guard=guard,
        trade_geometry=cert_geo,
        soft_prior_stops=True,
    )
    total_violations = int(constitution_violations) + int(rollout.constitution_violations)
    winrate = float(rollout.wins) / float(max(1, rollout.trades))
    sharpe = _sharpe_from_pnl(rollout.pnl_series)
    drawdown = _max_drawdown_pct(rollout.pnl_series)
    regimes = sorted(set(rollout.regimes_seen))
    regime_breakdown = build_oos_regime_breakdown(
        list(getattr(rollout, "trajectories", None) or [])
    )
    honest_pct = (
        real_data_percentage(holdout_data) if holdout_data else float(real_data_pct)
    )

    failure_reasons = build_certificate_failure_reasons(
        real_data_pct=honest_pct,
        winrate=winrate,
        sharpe=sharpe,
        drawdown=drawdown,
        regimes=regimes,
        holdout_trades=rollout.trades,
        constitution_violations=total_violations,
        thresholds=thresholds,
        regime_breakdown=regime_breakdown,
        holdout_ticks=list(holdout_data or []),
    )

    result = {
        "real_data_pct": float(honest_pct),
        "oos_winrate": round(winrate, 4),
        "oos_sharpe": round(sharpe, 4),
        "oos_max_drawdown_pct": round(drawdown, 4),
        "constitution_violations": total_violations,
        "regimes_covered": regimes[: max(3, len(regimes))],
        "holdout_days": int(holdout_days),
        "holdout_trades": rollout.trades,
        "oos_regime_breakdown": regime_breakdown,
        "failure_reasons": failure_reasons,
    }

    passed = len(failure_reasons) == 0
    result["certificate_passed"] = passed
    return result


def evaluate_multi_slice_micro_oos(
    *,
    runtime: Any,
    holdout_data: list[dict[str, Any]],
    policy: Any,
    real_data_pct: float,
    holdout_days: int,
    constitution_violations: int,
    workspace_root: Any,
    thresholds: BirthCertificateThresholds,
    max_trades: int = 800,
    slices: int = 3,
) -> dict[str, Any]:
    """Run micro-OOS on sequential holdout slices; mean WR with frozen cert thresholds."""
    n = max(1, int(slices))
    data = list(holdout_data or [])
    if len(data) < n * 10:
        return evaluate_holdout_certificate(
            runtime=runtime,
            holdout_data=data,
            policy=policy,
            real_data_pct=real_data_pct,
            holdout_days=holdout_days,
            constitution_violations=constitution_violations,
            workspace_root=workspace_root,
            thresholds=thresholds,
            max_trades=max_trades,
        )
    chunk = max(1, len(data) // n)
    slice_results: list[dict[str, Any]] = []
    for i in range(n):
        start = i * chunk
        end = len(data) if i == n - 1 else (i + 1) * chunk
        slice_data = data[start:end]
        if not slice_data:
            continue
        slice_results.append(
            evaluate_holdout_certificate(
                runtime=runtime,
                holdout_data=slice_data,
                policy=policy,
                real_data_pct=real_data_pct,
                holdout_days=holdout_days,
                constitution_violations=constitution_violations,
                workspace_root=workspace_root,
                thresholds=thresholds,
                max_trades=max(1, max_trades // n),
            )
        )
    if not slice_results:
        return evaluate_holdout_certificate(
            runtime=runtime,
            holdout_data=data,
            policy=policy,
            real_data_pct=real_data_pct,
            holdout_days=holdout_days,
            constitution_violations=constitution_violations,
            workspace_root=workspace_root,
            thresholds=thresholds,
            max_trades=max_trades,
        )
    mean_wr = sum(float(r.get("oos_winrate", 0.0) or 0.0) for r in slice_results) / float(
        len(slice_results)
    )
    # Full-holdout eval remains SSOT for certificate_passed; multi-slice is diagnostic.
    full = evaluate_holdout_certificate(
        runtime=runtime,
        holdout_data=data,
        policy=policy,
        real_data_pct=real_data_pct,
        holdout_days=holdout_days,
        constitution_violations=constitution_violations,
        workspace_root=workspace_root,
        thresholds=thresholds,
        max_trades=max_trades,
    )
    full["oos_multi_slice_winrate"] = round(mean_wr, 4)
    full["oos_multi_slice_count"] = len(slice_results)
    full["oos_multi_slice_winrates"] = [
        round(float(r.get("oos_winrate", 0.0) or 0.0), 4) for r in slice_results
    ]
    return full
