"""Per-config research diagnostics (researchers D14). Not a second gate."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from lumina_research.cycles.execution import ClosedTrade
from lumina_research.cycles.geometry import Geometry, family_break_even_win_rate
from lumina_research.validation.cost_model import CostedSeries
from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import RegimeSnapshot

UNBRACKET_HORIZONS: tuple[int, ...] = (16, 60, 120)


@dataclass(frozen=True, slots=True)
class ConfigDiagnostics:
    n_trades: int
    hitrate: float
    break_even_win_rate: float
    hitrate_minus_be: float
    gross_pnl: float
    net_pnl: float
    commission_usd: float
    half_spread_usd: float
    slippage_usd: float
    impact_usd: float
    is_sharpes: tuple[float, ...]
    oos_sharpes: tuple[float, ...]
    regime_vol_high: float
    regime_vol_low: float
    regime_trend_up: float
    regime_trend_down: float
    n_trials: int
    n_days: int
    pct_positive_oos: float
    bootstrap_sharpes: tuple[float, ...] = ()
    exit_stop: int = 0
    exit_target: int = 0
    exit_time_stop: int = 0
    exit_session_end: int = 0
    mean_mfe_ticks: float = float("nan")
    mean_mae_ticks: float = float("nan")
    hitrate_unbracket_n: float = float("nan")
    hitrate_1r1r: float = float("nan")
    gross_ticks: float = 0.0
    net_ticks: float = 0.0
    gross_points: float = 0.0
    net_points: float = 0.0
    unbracket_n_bars: int = 60
    hitrate_unbracket_16: float = float("nan")
    hitrate_unbracket_60: float = float("nan")
    hitrate_unbracket_120: float = float("nan")


def empty_diagnostics(*, be: float = math.nan, n_trials: int = 0, n_days: int = 0) -> ConfigDiagnostics:
    return ConfigDiagnostics(
        n_trades=0,
        hitrate=math.nan,
        break_even_win_rate=be,
        hitrate_minus_be=math.nan,
        gross_pnl=0.0,
        net_pnl=0.0,
        commission_usd=0.0,
        half_spread_usd=0.0,
        slippage_usd=0.0,
        impact_usd=0.0,
        is_sharpes=(),
        oos_sharpes=(),
        regime_vol_high=math.nan,
        regime_vol_low=math.nan,
        regime_trend_up=math.nan,
        regime_trend_down=math.nan,
        n_trials=n_trials,
        n_days=n_days,
        pct_positive_oos=math.nan,
        bootstrap_sharpes=(),
        exit_stop=0,
        exit_target=0,
        exit_time_stop=0,
        exit_session_end=0,
        mean_mfe_ticks=math.nan,
        mean_mae_ticks=math.nan,
        hitrate_unbracket_n=math.nan,
        hitrate_1r1r=math.nan,
        gross_ticks=0.0,
        net_ticks=0.0,
        gross_points=0.0,
        net_points=0.0,
        unbracket_n_bars=60,
        hitrate_unbracket_16=math.nan,
        hitrate_unbracket_60=math.nan,
        hitrate_unbracket_120=math.nan,
    )


def from_trades(
    *,
    trades: Sequence[ClosedTrade],
    geometry: Geometry,
    costed: CostedSeries,
    is_sharpes: Sequence[float],
    oos_sharpes: Sequence[float],
    regimes: RegimeSnapshot,
    n_trials: int,
    n_days: int,
    pct_positive_oos: float,
    bootstrap_sharpes: Sequence[float] = (),
    unbracket_trades: Sequence[ClosedTrade] = (),
    one_r_trades: Sequence[ClosedTrade] = (),
    unbracket_n_bars: int = 60,
    unbracket_by_horizon: Mapping[int, Sequence[ClosedTrade]] | None = None,
    target_atr: float | None = None,
    stop_atr: float | None = None,
    disable_brackets: bool = False,
) -> ConfigDiagnostics:
    n_trades = len(trades)
    wins = sum(1 for item in trades if item.pnl_ticks > 0.0)
    hitrate = math.nan if n_trades == 0 else wins / float(n_trades)
    be = family_break_even_win_rate(
        target_atr=target_atr,
        stop_atr=stop_atr,
        disable_brackets=disable_brackets,
        tick_geometry=geometry,
    )
    gross = float(sum(costed.gross_returns))
    net = float(sum(costed.net_returns))
    reasons = [item.reason for item in trades]
    mfe = tuple(item.mfe_ticks for item in trades)
    mae = tuple(item.mae_ticks for item in trades)
    gross_ticks = float(sum(item.pnl_ticks for item in trades))
    tick = geometry.tick_size
    cost_ticks = (
        0.0
        if tick <= 0.0
        else float(sum(costed.costs_usd)) / (geometry.tick_value_usd if geometry.tick_value_usd else 1.0)
    )
    net_ticks = gross_ticks - cost_ticks
    by_horizon = dict(unbracket_by_horizon or {})
    if unbracket_trades and int(unbracket_n_bars) not in by_horizon:
        by_horizon[int(unbracket_n_bars)] = unbracket_trades
    rate_16 = _hitrate(by_horizon.get(16, ()))
    rate_60 = _hitrate(by_horizon.get(60, ()))
    rate_120 = _hitrate(by_horizon.get(120, ()))
    unb_legacy = rate_60 if math.isfinite(rate_60) else _hitrate(unbracket_trades)
    r_n = len(one_r_trades)
    r_hits = sum(1 for item in one_r_trades if item.pnl_ticks > 0.0)
    return ConfigDiagnostics(
        n_trades=n_trades,
        hitrate=hitrate,
        break_even_win_rate=be,
        hitrate_minus_be=hitrate - be if math.isfinite(hitrate) else math.nan,
        gross_pnl=gross,
        net_pnl=net,
        commission_usd=float(sum(costed.commission_usd)),
        half_spread_usd=float(sum(costed.half_spread_usd)),
        slippage_usd=float(sum(costed.slippage_usd)),
        impact_usd=float(sum(costed.impact_usd)),
        is_sharpes=tuple(float(item) for item in is_sharpes),
        oos_sharpes=tuple(float(item) for item in oos_sharpes),
        regime_vol_high=regimes.vol_high_sharpe,
        regime_vol_low=regimes.vol_low_sharpe,
        regime_trend_up=regimes.trend_up_sharpe,
        regime_trend_down=regimes.trend_down_sharpe,
        n_trials=int(n_trials),
        n_days=int(n_days),
        pct_positive_oos=float(pct_positive_oos),
        bootstrap_sharpes=tuple(float(item) for item in bootstrap_sharpes),
        exit_stop=sum(1 for item in reasons if item == "stop"),
        exit_target=sum(1 for item in reasons if item == "target"),
        exit_time_stop=sum(1 for item in reasons if item == "time_stop"),
        exit_session_end=sum(1 for item in reasons if item == "session_end"),
        mean_mfe_ticks=sum(mfe) / float(len(mfe)) if mfe else math.nan,
        mean_mae_ticks=sum(mae) / float(len(mae)) if mae else math.nan,
        hitrate_unbracket_n=unb_legacy,
        hitrate_1r1r=math.nan if r_n == 0 else r_hits / float(r_n),
        gross_ticks=gross_ticks,
        net_ticks=net_ticks,
        gross_points=gross_ticks * tick,
        net_points=net_ticks * tick,
        unbracket_n_bars=int(unbracket_n_bars),
        hitrate_unbracket_16=rate_16,
        hitrate_unbracket_60=rate_60 if math.isfinite(rate_60) else unb_legacy,
        hitrate_unbracket_120=rate_120,
    )


def _hitrate(trades: Sequence[ClosedTrade]) -> float:
    n_trades = len(tuple(trades))
    if n_trades == 0:
        return math.nan
    wins = sum(1 for item in trades if item.pnl_ticks > 0.0)
    return wins / float(n_trades)


def window_sharpe(returns: Sequence[float]) -> float:
    return float(annualized_sharpe(returns))
