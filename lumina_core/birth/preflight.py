"""Birth data preflight — fail fast before multi-day curriculum (BRO v2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.birth.purged_split import PurgedSplit


@dataclass(slots=True)
class PreflightReport:
    ok: bool
    holdout_regimes: tuple[str, ...]
    holdout_tick_count: int
    holdout_days: int
    train_regimes: tuple[str, ...]
    estimated_holdout_trades: int
    message: str
    failure_reasons: tuple[str, ...] = ()


def regime_labels(ticks: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for tick in ticks:
        label = str(tick.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper()
        if label:
            out.add(label)
    return out


def estimate_holdout_trade_capacity(holdout_ticks: list[dict[str, Any]]) -> int:
    """Heuristic: ~1 closed trade per 80 holdout ticks under active policy."""
    if not holdout_ticks:
        return 0
    return max(1, len(holdout_ticks) // 80)


def assess_split_preflight(
    split: PurgedSplit,
    *,
    thresholds: BirthCertificateThresholds,
) -> PreflightReport:
    holdout_regimes = tuple(sorted(regime_labels(split.holdout)))
    train_regimes = tuple(sorted(regime_labels(split.train)))
    est_trades = estimate_holdout_trade_capacity(split.holdout)
    reasons: list[str] = []

    if len(holdout_regimes) < thresholds.min_regimes:
        reasons.append(
            f"holdout_regimes:{len(holdout_regimes)}/{thresholds.min_regimes}"
        )
    if est_trades < thresholds.min_holdout_trades:
        reasons.append(
            f"holdout_trade_capacity:{est_trades}/{thresholds.min_holdout_trades}"
        )
    if len(split.holdout) < 500:
        reasons.append(f"holdout_ticks:{len(split.holdout)}/500")

    ok = not reasons
    message = (
        "Holdout preflight OK"
        if ok
        else "Holdout preflight failed — expand history or adjust holdout slice"
    )
    return PreflightReport(
        ok=ok,
        holdout_regimes=holdout_regimes,
        holdout_tick_count=len(split.holdout),
        holdout_days=int(split.holdout_days),
        train_regimes=train_regimes,
        estimated_holdout_trades=est_trades,
        message=message,
        failure_reasons=tuple(reasons),
    )


def data_manifest_from_split(
    split: PurgedSplit,
    *,
    days_loaded: int,
    real_data_pct: float,
    train_hash: str = "",
) -> dict[str, Any]:
    holdout_regimes = sorted(regime_labels(split.holdout))
    return {
        "days_loaded": int(days_loaded),
        "train_hash": str(train_hash or ""),
        "holdout_regimes": holdout_regimes,
        "holdout_tick_count": len(split.holdout),
        "train_tick_count": len(split.train),
        "tick_count": len(split.train) + len(split.holdout),
        "holdout_days": int(split.holdout_days),
        "real_data_pct": float(real_data_pct),
        "ticks_cache_path": "",
        "split_cache_path": "",
    }
