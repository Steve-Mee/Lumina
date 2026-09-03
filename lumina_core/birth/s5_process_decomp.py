"""S5 process-R decomp: Gate 0 tables + birth close reward (M2 helper).

G0 tables are measurement. Birth close reward is signed process-R on the same
MES $5 booked dollars the exam writes to ``close_ledger.pnl``. Non-birth
reward stays in ``compute_expectancy_reward``.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from lumina_core.birth.birth_trade_geometry import MES_TICK_SIZE
from lumina_core.birth.notional_cap import birth_gym_point_value

CLOSE_REASONS = ("stop", "target", "time_stop", "flatten", "force_exit")
HOLDOUT_REGIMES = ("NEUTRAL", "TREND_DOWN", "TREND_UP")
PRE_GATE1_REWARD_CLASS = "mixed"
LIVE_REWARD_SITE = "lumina_core/rl/gym_environment_step.py:385"
BIRTH_PROCESS_R_SITE = "lumina_core/birth/s5_process_decomp.py:birth_close_process_r"


def birth_close_process_r(
    booked_pnl_usd: float,
    intended_risk_usd: float,
    *,
    tick_usd: float | None = None,
) -> float:
    """Signed process-R: booked exam dollars / intended risk. Same object as ledger."""
    tick = float(tick_usd) if tick_usd is not None else (
        MES_TICK_SIZE * birth_gym_point_value()
    )
    denom = max(float(intended_risk_usd), float(tick), 1e-9)
    return float(booked_pnl_usd) / denom


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = row.get(key)
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def _reason(row: dict[str, Any]) -> str:
    return str(row.get("close_reason") or row.get("reason") or "")


def _gap(row: dict[str, Any]) -> bool:
    return bool(row.get("gap"))


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    idx = min(len(sorted_vals) - 1, max(0, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return float(sorted_vals[idx])


def exit_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """G0.A — one row per close reason."""
    out: dict[str, dict[str, float]] = {}
    for reason in CLOSE_REASONS:
        bucket = [r for r in rows if _reason(r) == reason]
        out[reason] = _bucket_stats(bucket)
    return out


def gap_vs_clean_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """G0.B — reason ∧ gap / reason ∧ ¬gap for stop, target, time_stop."""
    out: dict[str, dict[str, float]] = {}
    for reason in ("target", "stop", "time_stop"):
        g = [r for r in rows if _reason(r) == reason and _gap(r)]
        c = [r for r in rows if _reason(r) == reason and not _gap(r)]
        out[f"{reason}_gap"] = _bucket_stats(g)
        out[f"{reason}_clean"] = _bucket_stats(c)
    return out


def target_clean_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for r in rows if _reason(r) == "target" and not _gap(r))


def regime_table(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """G0.C — holdout regimes plus any remainder the join actually yields."""
    labels = sorted({str(r.get("regime") or "UNKNOWN") for r in rows})
    ordered = [x for x in HOLDOUT_REGIMES if x in labels] + [
        x for x in labels if x not in HOLDOUT_REGIMES
    ]
    out: dict[str, dict[str, float]] = {}
    total_loss = sum(min(0.0, _f(r, "pnl")) for r in rows)
    for label in ordered:
        bucket = [r for r in rows if str(r.get("regime") or "UNKNOWN") == label]
        stats = _bucket_stats(bucket)
        share = 0.0
        if total_loss < 0.0:
            share = abs(min(0.0, stats["sum_usd"])) / abs(total_loss)
        stats["loss_share"] = float(share)
        out[label] = stats
    return out


def largest_loss_regime(table: dict[str, dict[str, float]]) -> tuple[str, float]:
    if not table:
        return "", 0.0
    name = max(table, key=lambda k: abs(float(table[k].get("sum_usd") or 0.0)))
    return name, float(table[name].get("loss_share") or 0.0)


def _bucket_stats(rows: list[dict[str, Any]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {
            "n": 0.0,
            "wins": 0.0,
            "wr": 0.0,
            "sum_usd": 0.0,
            "mean_usd": 0.0,
            "median_usd": 0.0,
            "mean_trade_r": 0.0,
            "p50_abs_trade_r": 0.0,
            "p95_abs_trade_r": 0.0,
            "max_abs_trade_r": 0.0,
            "cap_hit_n": 0.0,
        }
    pnls = [_f(r, "pnl") for r in rows]
    rs = [_f(r, "trade_r") for r in rows]
    abs_r = sorted(abs(x) for x in rs)
    wins = sum(1 for p in pnls if p > 0.0)
    cap_hits = 0
    for r in rows:
        if r.get("cap_hit") is True:
            cap_hits += 1
            continue
        pnl = abs(_f(r, "pnl"))
        cap = _f(r, "cap_usd")
        if cap > 0.0 and pnl + 1e-9 >= cap:
            cap_hits += 1
        elif abs(pnl - 501.25) < 1e-6:
            cap_hits += 1
    return {
        "n": float(n),
        "wins": float(wins),
        "wr": float(wins) / float(n),
        "sum_usd": float(sum(pnls)),
        "mean_usd": float(sum(pnls) / n),
        "median_usd": float(median(pnls)),
        "mean_trade_r": float(sum(rs) / n),
        "p50_abs_trade_r": _percentile(abs_r, 50.0),
        "p95_abs_trade_r": _percentile(abs_r, 95.0),
        "max_abs_trade_r": float(abs_r[-1]),
        "cap_hit_n": float(cap_hits),
    }


def classify_live_close_reward() -> str:
    """PR #13 live S5 close: mixed expectancy + occupancy, not signed process-R."""
    return PRE_GATE1_REWARD_CLASS


def evaluate_triggers(
    rows: list[dict[str, Any]],
    *,
    p_ft: float,
    force_open: int,
    gap_flag_honest: bool,
) -> dict[str, Any]:
    """M1→M4 in ticket order. First indicated AND implementable wins."""
    g0a = exit_table(rows)
    g0b = gap_vs_clean_table(rows)
    g0c = regime_table(rows)
    targets = int(g0a["target"]["n"])
    clean_targets = target_clean_count(rows)
    clean_frac = (float(clean_targets) / float(targets)) if targets else 1.0
    m1_count = clean_frac <= 0.05
    m1 = bool(m1_count and not gap_flag_honest)

    live = classify_live_close_reward()
    m2 = live != "process-R"

    ts = g0a["time_stop"]
    ts_share = (ts["n"] / float(len(rows))) if rows else 0.0
    m3 = bool(
        ts_share >= 0.20
        and ts["mean_usd"] < 0.0
        and ts["mean_trade_r"] <= -0.25
        and ts["p95_abs_trade_r"] < 3.0
    )

    wreck, share = largest_loss_regime(g0c)
    wreck_wr = float(g0c.get(wreck, {}).get("wr") or 0.0)
    m4 = bool(share >= 0.70 and wreck_wr <= float(p_ft) - 0.05)

    shipped = "none"
    if m1:
        shipped = "M1"
    elif m2:
        shipped = "M2"
    elif m3:
        shipped = "M3"
    elif m4:
        shipped = "M4"

    return {
        "m1_indicated": m1,
        "m1_count_trip": m1_count,
        "m1_clean_targets": clean_targets,
        "m1_clean_frac": clean_frac,
        "m1_gap_flag_honest": gap_flag_honest,
        "m2_indicated": m2,
        "m2_reward_class": live,
        "m3_indicated": m3,
        "m3_time_stop_share": ts_share,
        "m3_time_stop_mean_usd": ts["mean_usd"],
        "m3_time_stop_mean_r": ts["mean_trade_r"],
        "m3_time_stop_p95_abs_r": ts["p95_abs_trade_r"],
        "m4_indicated": m4,
        "m4_wreck_regime": wreck,
        "m4_loss_share": share,
        "m4_wreck_wr": wreck_wr,
        "gate1": shipped,
        "force_open": int(force_open),
        "g0a": g0a,
        "g0b": g0b,
        "g0c": g0c,
    }


__all__ = [
    "BIRTH_PROCESS_R_SITE",
    "LIVE_REWARD_SITE",
    "PRE_GATE1_REWARD_CLASS",
    "birth_close_process_r",
    "classify_live_close_reward",
    "evaluate_triggers",
    "exit_table",
    "gap_vs_clean_table",
    "largest_loss_regime",
    "regime_table",
    "target_clean_count",
]
