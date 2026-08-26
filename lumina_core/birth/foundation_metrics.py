"""Birth Foundation metric SSOT (ADR-0046).

Pass, HUD, receipt, DNA, and UI import these functions. No local WR/BE/R copies.
Rolling WR is HUD-only. WR−0.50 expectancy is diagnostic, never ``passed``.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from lumina_core.birth.birth_trade_geometry import MES_POINT_VALUE_USD

FOUNDATION_SCHEMA = "foundation_v2"
FOUNDATION_STAGE_COUNT = 5
REPLAY_TRADES_PER_UNIQUE_DAY = 40
MEDIAN_LOSS_R_MAX = 1.5
NET_RR_MIN = 0.80
SETTLEMENT_MIN_SHARE = 0.70
S3_EDGE_MIN = -0.05
S4_EDGE_MIN = 0.0
S4_MEAN_R_SLACK = 0.10
S5_EDGE_MIN = -0.03
S5_SHARPE_FLOOR = -2.0
S5_DD_MAX_PCT = 25.0
S5_DD_EQUITY_USD = 50_000.0
S1_MIN_TRADES = 150
S2_MIN_TRADES = 250
S3_MIN_TRADES = 400
S4_MIN_TRADES = 100
S5_MIN_TRADES = 50
S2_OCCUPANCY_MIN = 0.30
S2_OCCUPANCY_MAX = 0.70
S3_OCCUPANCY_MIN = 0.25
S3_OCCUPANCY_MAX = 0.75


def stop_usd(
    *,
    stop_pct: float,
    ref_price: float,
    point_value: float = MES_POINT_VALUE_USD,
    qty: int = 1,
) -> float:
    """Intended stop risk in USD. Qty defaults to 1 (nursery / tests)."""
    return intended_risk_usd(
        stop_pct=stop_pct,
        entry_price=ref_price,
        qty=qty,
        point_value=point_value,
    )


def intended_risk_usd(
    *,
    stop_pct: float,
    entry_price: float,
    qty: int = 1,
    point_value: float = MES_POINT_VALUE_USD,
) -> float:
    """Dollars consciously risked: |stop| × price × contracts × point value.

    Floor is numeric only (1e-9). Never invent a $25 equity theater floor.
    """
    n = max(1, int(qty))
    raw = abs(float(stop_pct)) * abs(float(entry_price)) * float(n) * abs(float(point_value))
    return max(raw, 1e-9)


def r_multiples(pnl_series: list[float], *, stop_usd_value: float) -> list[float]:
    denom = max(float(stop_usd_value), 1e-9)
    return [float(pnl) / denom for pnl in pnl_series]


def r_multiples_from_risk(
    pnl_series: list[float],
    risk_series: list[float],
) -> list[float]:
    """Per-trade R when each close has its own intended risk."""
    out: list[float] = []
    for pnl, risk in zip(pnl_series, risk_series, strict=False):
        out.append(float(pnl) / max(float(risk), 1e-9))
    return out


def mean_r(rs: list[float]) -> float | None:
    if not rs:
        return None
    return float(sum(rs) / float(len(rs)))


def median_loss_r(rs: list[float]) -> float | None:
    """Process health: typical losing trade in R. None if no closed trades."""
    if not rs:
        return None
    losses = [abs(float(r)) for r in rs if float(r) < 0.0]
    if not losses:
        return 0.0
    return float(median(losses))


def occupancy_ratio(*, flat_bars: int, total_signals: int) -> float | None:
    """Plant-flat occupancy. Never HOLD%. None when the denominator is missing."""
    total = int(total_signals)
    if total <= 0:
        return None
    return float(max(0, int(flat_bars))) / float(total)


def mechanical_ev_r(*, p_ft: float, net_rr: float) -> float:
    p = max(0.0, min(1.0, float(p_ft)))
    rr = float(net_rr)
    return p * rr - (1.0 - p) * 1.0


def skill_edge(*, skill_wr: float, p_ft: float) -> float:
    return float(skill_wr) - float(p_ft)


def skill_winrate(*, trades: int, wins: int) -> float:
    n = max(0, int(trades))
    if n <= 0:
        return 0.0
    return float(max(0, int(wins))) / float(n)


def replay_cap_ok(
    *,
    trades: int,
    unique_calendar_days: int,
    cap: int = REPLAY_TRADES_PER_UNIQUE_DAY,
) -> bool:
    days = int(unique_calendar_days)
    if days <= 0:
        return False
    return int(trades) <= int(cap) * days


def process_r_ok(median_loss: float | None, *, max_r: float = MEDIAN_LOSS_R_MAX) -> bool:
    if median_loss is None:
        return False
    return float(median_loss) <= float(max_r) + 1e-12


@dataclass(frozen=True, slots=True)
class FoundationSnapshot:
    """Single physics snapshot consumed by pass, HUD, receipt, DNA, UI."""

    trades: int
    wins: int
    skill_wr: float
    occupancy: float | None
    median_loss_r: float | None
    mean_r: float | None
    p_ft: float | None
    net_rr: float | None
    e_mech: float | None
    edge: float | None
    settlement_ok: bool
    settlement_share: float
    constitution_violations: int
    entropy_alive: bool
    unique_calendar_days: int
    replay_ok: bool
    oos_sharpe: float | None = None
    oos_dd_pct: float | None = None
    schema: str = FOUNDATION_SCHEMA

    def to_progress_fields(self) -> dict[str, Any]:
        return {
            "foundation_schema": self.schema,
            "median_loss_r": self.median_loss_r,
            "mean_r": self.mean_r,
            "occupancy": self.occupancy,
            "first_touch_p_ft": self.p_ft,
            "geometry_net_rr": self.net_rr,
            "e_mech": self.e_mech,
            "edge_vs_first_touch": self.edge,
            "foundation_skill_wr": self.skill_wr,
            "foundation_replay_ok": self.replay_ok,
            "foundation_unique_calendar_days": self.unique_calendar_days,
            "oos_sharpe": self.oos_sharpe,
            "oos_dd_pct": self.oos_dd_pct,
        }


def build_foundation_snapshot(
    *,
    trades: int,
    wins: int,
    pnl_series: list[float] | None = None,
    r_series: list[float] | None = None,
    stop_pct: float | None = None,
    ref_price: float | None = None,
    qty: int = 1,
    net_rr: float | None = None,
    p_ft: float | None = None,
    median_loss_r_value: float | None = None,
    mean_r_value: float | None = None,
    flat_bars: int = 0,
    total_signals: int = 0,
    occupancy: float | None = None,
    settlement_ok: bool = False,
    settlement_share: float = 0.0,
    constitution_violations: int = 0,
    entropy_alive: bool = False,
    unique_calendar_days: int = 0,
    oos_sharpe: float | None = None,
    oos_dd_pct: float | None = None,
    replay_cap: int = REPLAY_TRADES_PER_UNIQUE_DAY,
) -> FoundationSnapshot:
    n = max(0, int(trades))
    w = max(0, int(wins))
    wr = skill_winrate(trades=n, wins=w)
    occ = occupancy if occupancy is not None else occupancy_ratio(
        flat_bars=flat_bars, total_signals=total_signals
    )
    med = median_loss_r_value
    mean = mean_r_value
    rs: list[float] | None = None
    if r_series is not None:
        rs = [float(x) for x in r_series]
    elif pnl_series and stop_pct is not None and ref_price is not None:
        usd = stop_usd(
            stop_pct=float(stop_pct),
            ref_price=float(ref_price),
            qty=int(qty),
        )
        rs = r_multiples([float(x) for x in pnl_series], stop_usd_value=usd)
    if rs:
        if med is None:
            med = median_loss_r(rs)
        if mean is None:
            mean = mean_r(rs)
    rr = float(net_rr) if net_rr is not None else None
    p = float(p_ft) if p_ft is not None else None
    e_mech = mechanical_ev_r(p_ft=p, net_rr=rr) if p is not None and rr is not None else None
    edge = skill_edge(skill_wr=wr, p_ft=p) if p is not None else None
    days = max(0, int(unique_calendar_days))
    return FoundationSnapshot(
        trades=n,
        wins=w,
        skill_wr=wr,
        occupancy=occ,
        median_loss_r=med,
        mean_r=mean,
        p_ft=p,
        net_rr=rr,
        e_mech=e_mech,
        edge=edge,
        settlement_ok=bool(settlement_ok),
        settlement_share=float(settlement_share),
        constitution_violations=max(0, int(constitution_violations)),
        entropy_alive=bool(entropy_alive),
        unique_calendar_days=days,
        replay_ok=replay_cap_ok(trades=n, unique_calendar_days=days, cap=int(replay_cap)),
        oos_sharpe=float(oos_sharpe) if oos_sharpe is not None else None,
        oos_dd_pct=float(oos_dd_pct) if oos_dd_pct is not None else None,
    )


__all__ = [
    "FOUNDATION_SCHEMA",
    "FOUNDATION_STAGE_COUNT",
    "MEDIAN_LOSS_R_MAX",
    "NET_RR_MIN",
    "REPLAY_TRADES_PER_UNIQUE_DAY",
    "S1_MIN_TRADES",
    "S2_MIN_TRADES",
    "S3_MIN_TRADES",
    "S4_MEAN_R_SLACK",
    "S4_MIN_TRADES",
    "S5_DD_EQUITY_USD",
    "S5_DD_MAX_PCT",
    "S5_MIN_TRADES",
    "S5_SHARPE_FLOOR",
    "FoundationSnapshot",
    "build_foundation_snapshot",
    "intended_risk_usd",
    "mechanical_ev_r",
    "median_loss_r",
    "mean_r",
    "occupancy_ratio",
    "process_r_ok",
    "r_multiples",
    "r_multiples_from_risk",
    "replay_cap_ok",
    "skill_edge",
    "skill_winrate",
    "stop_usd",
]
