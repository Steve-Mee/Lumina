"""VaR calculation helpers for PortfolioVaRAllocator (global residual)."""
from __future__ import annotations

import logging
from statistics import NormalDist
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from lumina_core.engine.portfolio_var_allocator import PortfolioVaRSnapshot

logger = logging.getLogger(__name__)


def _PortfolioVaRSnapshot(**kwargs) -> "PortfolioVaRSnapshot":
    from lumina_core.engine.portfolio_var_allocator import PortfolioVaRSnapshot
    return PortfolioVaRSnapshot(**kwargs)

class PortfolioVaRCalcMixin:
    def _returns_frame(self, exposures: dict[str, float]) -> pd.DataFrame | None:
        if not exposures:
            return None

        window_points = max(self.config.min_points, int(self.config.window_days) * 24 * 60)
        series_by_symbol: dict[str, pd.Series] = {}
        for symbol in exposures:
            closes = self._symbol_close_series(symbol, window_points=window_points)
            if closes is None or closes.empty:
                continue
            returns = closes.pct_change().dropna()
            if len(returns) >= self.config.min_points:
                series_by_symbol[symbol] = returns

        if not series_by_symbol:
            return None

        returns_df = pd.DataFrame(series_by_symbol).dropna(how="any")
        if returns_df.empty:
            return None
        return returns_df.tail(window_points)
    def _symbol_close_series(self, symbol: str, *, window_points: int) -> pd.Series | None:
        manager = self.swarm_manager
        key = str(symbol).strip().upper()

        if manager is not None:
            nodes = getattr(manager, "nodes", {})
            node = nodes.get(key) if isinstance(nodes, dict) else None
            if node is not None:
                market_data = getattr(node, "market_data", None)
                if market_data is not None and hasattr(market_data, "copy_ohlc"):
                    ohlc = market_data.copy_ohlc()
                    if isinstance(ohlc, pd.DataFrame) and "close" in ohlc.columns and len(ohlc) > 1:
                        return pd.to_numeric(ohlc["close"], errors="coerce").dropna().tail(window_points)

                prices_rolling = list(getattr(node, "prices_rolling", []) or [])
                if len(prices_rolling) > 1:
                    return pd.Series(prices_rolling, dtype=float).tail(window_points)

        return None
    def _portfolio_pnl_series(self, *, exposures: dict[str, float], returns_df: pd.DataFrame) -> pd.Series:
        per_symbol_pnl: dict[str, pd.Series] = {}
        for symbol, exposure in exposures.items():
            if symbol not in returns_df.columns:
                continue
            point_value = max(0.01, float(self.valuation_engine.point_value(symbol)))
            contracts = max(0.1, float(exposure) / max(1.0, point_value * 10.0))
            returns = returns_df[symbol]
            # Dollar PnL approximation using contract scaling derived from valuation specs.
            per_symbol_pnl[symbol] = returns * point_value * contracts * 100.0

        if not per_symbol_pnl:
            return pd.Series(dtype=float)

        pnl_df = pd.DataFrame(per_symbol_pnl).dropna(how="any")
        if pnl_df.empty:
            return pd.Series(dtype=float)
        return pnl_df.sum(axis=1)
    def _calculate_var_usd(
        self,
        pnl_series: pd.Series,
        *,
        exposures: dict[str, float],
        returns_df: pd.DataFrame,
    ) -> float:
        if pnl_series.empty:
            return 0.0

        losses = (-pnl_series).dropna()
        if losses.empty:
            return 0.0

        confidence = min(0.999, max(0.5, float(self.config.confidence)))
        method = str(self.config.method).strip().lower()

        if method == "parametric":
            mean = float(losses.mean())
            std = float(losses.std(ddof=1))
            if std <= 0.0:
                return max(0.0, mean)
            z = NormalDist().inv_cdf(confidence)
            return max(0.0, mean + (z * std))

        if method == "scenario":
            historical_var = max(0.0, float(losses.quantile(confidence)))
            scenario_var = self._scenario_var_usd(exposures=exposures, returns_df=returns_df)
            return max(historical_var, scenario_var)

        # Default method: historical VaR
        return max(0.0, float(losses.quantile(confidence)))
    def _scenario_var_usd(self, *, exposures: dict[str, float], returns_df: pd.DataFrame) -> float:
        shocks = self.config.scenario_shocks or {"base": 0.03, "volatile": 0.06}
        base_shock = max(0.0, float(shocks.get("base", 0.03)))
        volatile_shock = max(base_shock, float(shocks.get("volatile", 0.06)))
        tail_p = min(0.2, max(0.001, float(self.config.scenario_tail_percentile)))

        total = 0.0
        for symbol, exposure in exposures.items():
            series = returns_df.get(symbol)
            if series is None or series.empty:
                total += float(exposure) * base_shock
                continue
            tail_return = float(series.quantile(tail_p))
            empirical_shock = abs(min(0.0, tail_return))
            shock = max(base_shock, min(volatile_shock, empirical_shock * 1.5))
            total += float(exposure) * shock
        return max(0.0, total)
    def _snapshot(
        self,
        *,
        var_usd: float,
        total_open_risk: float,
        data_points: int,
        quality_score: float,
        quality_band: str,
        effective_max_var_usd: float,
        effective_max_total_open_risk: float,
        breached: bool,
        reason: str,
        symbols: list[str],
        correlation_matrix: dict[str, dict[str, float]],
        projected_drawdown_pre_pct: float,
        projected_drawdown_post_pct: float,
    ) -> PortfolioVaRSnapshot:
        return _PortfolioVaRSnapshot(
            var_usd=float(var_usd),
            max_var_usd=float(self.config.max_var_usd),
            total_open_risk=float(total_open_risk),
            max_total_open_risk=float(self.config.max_total_open_risk),
            confidence=float(self.config.confidence),
            window_days=int(self.config.window_days),
            method=str(self.config.method),
            data_points=int(data_points),
            quality_score=float(quality_score),
            quality_band=str(quality_band),
            effective_max_var_usd=float(effective_max_var_usd),
            effective_max_total_open_risk=float(effective_max_total_open_risk),
            breached=bool(breached),
            reason=str(reason),
            symbols=list(symbols),
            correlation_matrix=correlation_matrix,
            projected_drawdown_pre_pct=float(projected_drawdown_pre_pct),
            projected_drawdown_post_pct=float(projected_drawdown_post_pct),
            projected_drawdown_delta_pct=float(projected_drawdown_post_pct - projected_drawdown_pre_pct),
        )
    @staticmethod
    def _projected_drawdown_pct(total_open_risk: float, effective_limit: float) -> float:
        if effective_limit <= 0.0:
            return 0.0
        utilization = max(0.0, float(total_open_risk) / float(effective_limit))
        return float(min(100.0, utilization * 100.0))

    def _quality_score(self, data_points: int) -> float:
        points = max(0, int(data_points))
        minimum = max(1, int(self.config.min_points))
        # 0..100 score with bonus for deeper history, capped at 100.
        return (
            max(0.0, min(100.0, (points / float(minimum)) * 50.0 + 50.0))
            if points >= minimum
            else max(0.0, (points / float(minimum)) * 50.0)
        )
    def _quality_band(self, score: float) -> str:
        if score >= float(self.config.quality_green_min):
            return "green"
        if score >= float(self.config.quality_amber_min):
            return "amber"
        return "red"
    def _effective_limits(self, band: str) -> tuple[float, float]:
        base_var = float(self.config.max_var_usd)
        base_total = float(self.config.max_total_open_risk)
        b = str(band).strip().lower()
        if b == "amber":
            return (
                base_var * float(self.config.amber_var_limit_multiplier),
                base_total * float(self.config.amber_total_open_risk_multiplier),
            )
        if b == "red":
            return (
                base_var * float(self.config.red_var_limit_multiplier),
                base_total * float(self.config.red_total_open_risk_multiplier),
            )
        return base_var, base_total
    def _record_observability(self, snapshot: PortfolioVaRSnapshot) -> None:
        obs = self.observability_service
        if obs is None or not hasattr(obs, "record_portfolio_var"):
            return
        try:
            obs.record_portfolio_var(
                var_usd=float(snapshot.var_usd),
                max_var_usd=float(snapshot.max_var_usd),
                total_open_risk=float(snapshot.total_open_risk),
                breached=bool(snapshot.breached),
                method=str(snapshot.method),
                confidence=float(snapshot.confidence),
                symbols=list(snapshot.symbols),
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/portfolio_var_allocator.py:437")
            return
