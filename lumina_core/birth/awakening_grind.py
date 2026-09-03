"""Awakening grind: evaluate-only classifiers + Birth-SSOT metrics table.

Does not train. Does not move Birth floors. Stability bounds are ticket constants,
not new S5 pass floors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.foundation_metrics import (
    S5_DD_EQUITY_USD,
    build_foundation_snapshot,
    occupancy_ratio,
)
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.s5_process_decomp import target_clean_count

TRAIN = False

# Ticket Gate 1 bounds. Do not retune after seeing numbers.
BIRTH_N = 172
BIRTH_MEAN_USD = -20.7
REGRESS_MEAN_USD = -62.0
STABLE_SHARPE_GT = -2.0
REGRESS_SHARPE_LE = -3.0
STABLE_DD_MAX_PCT = 25.0
ONE_WAY_DD_PCT = 50.0
ADR0026_MIN_TRADES = 500

CLASS_STABLE = "STABLE"
CLASS_REGRESS = "GRIND_REGRESS"
CLASS_INCONCLUSIVE = "INCONCLUSIVE"

OVERALL_STABLE = "GRIND_STABLE_AWAKENING_OPEN"
OVERALL_REGRESS = "GRIND_REGRESS_AWAKENING_OPEN"
OVERALL_INCONCLUSIVE = "GRIND_INCONCLUSIVE_AWAKENING_OPEN"

GRIND_A_NAME = "grind_A_close_ledger.jsonl"
GRIND_B_NAME = "grind_B_close_ledger.jsonl"


@dataclass(slots=True)
class GrindLegMetrics:
    n: int = 0
    wins: int = 0
    wr: float = 0.0
    mean_usd: float = 0.0
    sum_usd: float = 0.0
    mean_r: float | None = None
    e_mech: float | None = None
    oos_sharpe: float = 0.0
    oos_dd_pct: float = 0.0
    edge: float | None = None
    plant: int = 0
    force_open: int = 0
    occupancy: float | None = None
    closes_stop: int = 0
    closes_target: int = 0
    closes_time_stop: int = 0
    closes_flatten: int = 0
    closes_unknown: int = 0
    target_clean: int = 0
    cap_hit_n: int = 0
    cap_hit_frac: float = 0.0
    loss_share_by_regime: dict[str, float] = field(default_factory=dict)
    policy_trades: int = 0
    p_ft: float | None = None
    realized_r_mean: float | None = None
    holdout_exhausted: bool = False
    frozen_loaded: bool = False
    frozen_path: str = ""
    frozen_sha256: str = ""
    start_bar_index: int = 0
    start_choice: str = "full_holdout_replay_frozen"
    optimizer_steps: int = 0
    train: bool = TRAIN
    classification: str = CLASS_INCONCLUSIVE


class EvaluateOnlyPolicy:
    """Wrapper that refuses PPO updates. Predict-only."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.optimizer_steps = 0
        self.last_open_signal: dict[str, Any] | None = None

    @property
    def policy(self) -> Any:
        return getattr(self._inner, "policy", None)

    def predict(self, *args: Any, **kwargs: Any) -> Any:
        raw = self._inner.predict(*args, **kwargs)
        obs = args[0] if args else kwargs.get("observation")
        action = raw[0] if isinstance(raw, (tuple, list)) and raw else raw
        from lumina_core.birth.policy_signal_extract import extract_policy_signals

        self.last_open_signal = extract_policy_signals(self._inner, obs, action)
        return raw

    def learn(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("awakening grind train=False — learn() forbidden")

    def set_training_mode(self, mode: bool = True) -> None:
        if mode:
            raise RuntimeError("awakening grind train=False — training mode forbidden")


def classify_grind_leg(
    *,
    n: int,
    oos_sharpe: float,
    oos_dd_pct: float,
    mean_usd: float,
    holdout_exhausted: bool,
    frozen_loaded: bool,
    full_series_dd_pct: float | None = None,
) -> str:
    """Exact Gate 1 strings. Remainder is fail-closed INCONCLUSIVE."""
    if not frozen_loaded or int(n) < BIRTH_N:
        return CLASS_INCONCLUSIVE
    dd = float(oos_dd_pct)
    full_dd = float(full_series_dd_pct) if full_series_dd_pct is not None else dd
    sharpe = float(oos_sharpe)
    mean = float(mean_usd)
    if (
        sharpe <= REGRESS_SHARPE_LE
        or dd > STABLE_DD_MAX_PCT
        or mean <= REGRESS_MEAN_USD
        or full_dd > ONE_WAY_DD_PCT
    ):
        return CLASS_REGRESS
    n_ok = int(n) >= ADR0026_MIN_TRADES or (
        bool(holdout_exhausted) and int(n) >= BIRTH_N
    )
    if (
        n_ok
        and sharpe > STABLE_SHARPE_GT
        and dd <= STABLE_DD_MAX_PCT
        and mean > REGRESS_MEAN_USD
        and sharpe > REGRESS_SHARPE_LE
    ):
        return CLASS_STABLE
    return CLASS_INCONCLUSIVE


def classify_overall(class_a: str, class_b: str) -> str:
    if class_a == CLASS_REGRESS or class_b == CLASS_REGRESS:
        return OVERALL_REGRESS
    if class_a == CLASS_STABLE and class_b == CLASS_STABLE:
        return OVERALL_STABLE
    return OVERALL_INCONCLUSIVE


def _f(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    raw = row.get(key)
    try:
        return float(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


def grind_table_from_rows(
    rows: list[dict[str, Any]],
    *,
    rollout: Any | None = None,
    p_ft: float | None = None,
    net_rr: float | None = None,
    holdout_exhausted: bool = False,
    frozen_loaded: bool = True,
    frozen_path: str = "",
    frozen_sha256: str = "",
) -> GrindLegMetrics:
    pnl = [_f(r, "pnl") for r in rows]
    n = len(pnl)
    wins = sum(1 for x in pnl if x > 0.0)
    sum_usd = float(sum(pnl))
    mean_usd = (sum_usd / float(n)) if n else 0.0
    rs = [_f(r, "trade_r") for r in rows if r.get("trade_r") is not None]
    if not rs:
        rs = [
            _f(r, "pnl") / max(_f(r, "intended_risk_usd", _f(r, "risk_usd")), 1e-9)
            for r in rows
        ]
    sharpe, dd = risk_metrics_from_pnl(pnl) if n else (0.0, 0.0)
    plant = int(getattr(rollout, "plant_trades", 0) or 0) if rollout is not None else sum(
        1 for r in rows if r.get("plant")
    )
    policy_n = n - plant
    if rollout is not None:
        policy_n = int(getattr(rollout, "policy_trades", policy_n) or policy_n)
    occ = None
    if rollout is not None:
        occ = occupancy_ratio(
            flat_bars=int(getattr(rollout, "range_flat_bars", 0) or 0),
            total_signals=int(getattr(rollout, "range_total_signals", 0) or 0),
        )
    cap_n = sum(1 for r in rows if bool(r.get("cap_hit")))
    from lumina_core.birth.s5_process_decomp import regime_table

    regime = regime_table(rows) if rows else {}
    loss_share = {k: float(v.get("loss_share") or 0.0) for k, v in regime.items()}
    snap = build_foundation_snapshot(
        trades=n,
        wins=wins,
        pnl_series=pnl,
        r_series=rs,
        p_ft=p_ft,
        net_rr=net_rr,
        occupancy=occ,
        skill_trades=max(0, policy_n),
        skill_wins=wins if plant == 0 else max(0, wins - int(getattr(rollout, "plant_wins", 0) or 0)),
        oos_sharpe=sharpe,
        oos_dd_pct=dd,
    )

    def _reason_count(name: str) -> int:
        return sum(1 for r in rows if str(r.get("close_reason") or "") == name)

    metrics = GrindLegMetrics(
        n=n,
        wins=wins,
        wr=float(snap.skill_wr or 0.0),
        mean_usd=mean_usd,
        sum_usd=sum_usd,
        mean_r=snap.mean_r,
        e_mech=snap.e_mech,
        oos_sharpe=sharpe,
        oos_dd_pct=dd,
        edge=snap.edge,
        plant=plant,
        force_open=int(getattr(rollout, "participation_force_open", 0) or 0)
        if rollout is not None
        else 0,
        occupancy=occ,
        closes_stop=int(getattr(rollout, "closes_stop", 0) or 0) if rollout is not None else _reason_count("stop"),
        closes_target=int(getattr(rollout, "closes_target", 0) or 0)
        if rollout is not None
        else _reason_count("target"),
        closes_time_stop=int(getattr(rollout, "closes_time_stop", 0) or 0)
        if rollout is not None
        else _reason_count("time_stop"),
        closes_flatten=int(getattr(rollout, "closes_flatten", 0) or 0)
        if rollout is not None
        else _reason_count("flatten") + _reason_count("force_exit"),
        closes_unknown=int(getattr(rollout, "closes_unknown", 0) or 0)
        if rollout is not None
        else _reason_count(""),
        target_clean=target_clean_count(rows),
        cap_hit_n=cap_n,
        cap_hit_frac=(float(cap_n) / float(n)) if n else 0.0,
        loss_share_by_regime=loss_share,
        policy_trades=max(0, policy_n),
        p_ft=p_ft,
        realized_r_mean=snap.mean_r,
        holdout_exhausted=bool(holdout_exhausted),
        frozen_loaded=bool(frozen_loaded),
        frozen_path=frozen_path,
        frozen_sha256=frozen_sha256,
        optimizer_steps=0,
        train=TRAIN,
    )
    metrics.classification = classify_grind_leg(
        n=metrics.n,
        oos_sharpe=metrics.oos_sharpe,
        oos_dd_pct=metrics.oos_dd_pct,
        mean_usd=metrics.mean_usd,
        holdout_exhausted=metrics.holdout_exhausted,
        frozen_loaded=metrics.frozen_loaded,
        full_series_dd_pct=metrics.oos_dd_pct,
    )
    return metrics


def metrics_as_table(m: GrindLegMetrics) -> dict[str, Any]:
    return {
        "n": m.n,
        "wr": m.wr,
        "mean_usd": m.mean_usd,
        "sum_usd": m.sum_usd,
        "mean_r": m.mean_r,
        "e_mech": m.e_mech,
        "sharpe": m.oos_sharpe,
        "dd_pct_of_50k": m.oos_dd_pct,
        "dd_equity_usd": S5_DD_EQUITY_USD,
        "edge": m.edge,
        "plant": m.plant,
        "FORCE_OPEN": m.force_open,
        "occ": m.occupancy,
        "exits": {
            "stop": m.closes_stop,
            "target": m.closes_target,
            "time_stop": m.closes_time_stop,
            "flatten": m.closes_flatten,
            "unknown": m.closes_unknown,
        },
        "target_and_not_gap": m.target_clean,
        "cap_hit_frac": m.cap_hit_frac,
        "loss_share_by_regime": dict(m.loss_share_by_regime),
        "realized_r_mean": m.realized_r_mean,
        "p_ft": m.p_ft,
        "classification": m.classification,
        "holdout_exhausted": m.holdout_exhausted,
        "frozen_loaded": m.frozen_loaded,
        "start_bar_index": m.start_bar_index,
        "start_choice": m.start_choice,
        "optimizer_steps": m.optimizer_steps,
        "train": m.train,
    }


__all__ = [
    "ADR0026_MIN_TRADES",
    "BIRTH_MEAN_USD",
    "BIRTH_N",
    "CLASS_INCONCLUSIVE",
    "CLASS_REGRESS",
    "CLASS_STABLE",
    "EvaluateOnlyPolicy",
    "GRIND_A_NAME",
    "GRIND_B_NAME",
    "GrindLegMetrics",
    "OVERALL_INCONCLUSIVE",
    "OVERALL_REGRESS",
    "OVERALL_STABLE",
    "REGRESS_MEAN_USD",
    "TRAIN",
    "classify_grind_leg",
    "classify_overall",
    "grind_table_from_rows",
    "metrics_as_table",
]
