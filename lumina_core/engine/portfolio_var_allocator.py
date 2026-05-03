from __future__ import annotations
import logging

from dataclasses import dataclass
from statistics import NormalDist
from typing import Any

import pandas as pd

from .valuation_engine import ValuationEngine


@dataclass(slots=True)
class PortfolioVaRSnapshot:
    var_usd: float
    max_var_usd: float
    total_open_risk: float
    max_total_open_risk: float
    confidence: float
    window_days: int
    method: str
    data_points: int
    quality_score: float
    quality_band: str
    effective_max_var_usd: float
    effective_max_total_open_risk: float
    breached: bool
    reason: str
    symbols: list[str]
    correlation_matrix: dict[str, dict[str, float]]
    projected_drawdown_pre_pct: float
    projected_drawdown_post_pct: float
    projected_drawdown_delta_pct: float


@dataclass(slots=True)
class PortfolioVaRConfig:
    confidence: float = 0.95
    window_days: int = 30
    max_var_usd: float = 1200.0
    max_total_open_risk: float = 3000.0
    method: str = "historical"
    min_points: int = 20
    enforce_fail_closed: bool = True
    quality_green_min: float = 80.0
    quality_amber_min: float = 55.0
    amber_var_limit_multiplier: float = 0.85
    amber_total_open_risk_multiplier: float = 0.9
    red_var_limit_multiplier: float = 0.7
    red_total_open_risk_multiplier: float = 0.8
    scenario_shocks: dict[str, float] | None = None
    scenario_tail_percentile: float = 0.02


class PortfolioVaRAllocator:
    """Portfolio-level VaR guardrail for multi-symbol swarm exposure."""

    def __init__(
        self,
        *,
        valuation_engine: ValuationEngine,
        swarm_manager: Any | None = None,
        observability_service: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.valuation_engine = valuation_engine
        self.swarm_manager = swarm_manager
        self.observability_service = observability_service
        self.config = self._parse_config(config or {})

    @staticmethod
    def _parse_config(raw: dict[str, Any]) -> PortfolioVaRConfig:
        # Keep backward compatibility with max_var_usd while preferring the spec key.
        max_var_raw = raw.get("max_portfolio_var_usd", raw.get("max_var_usd", 1200.0))
        return PortfolioVaRConfig(
            confidence=float(raw.get("confidence", 0.95) or 0.95),
            window_days=max(1, int(raw.get("window_days", 30) or 30)),
            max_var_usd=float(max_var_raw or 1200.0),
            max_total_open_risk=float(raw.get("max_total_open_risk", 3000.0) or 3000.0),
            method=str(raw.get("method", "historical") or "historical").strip().lower(),
            min_points=max(10, int(raw.get("min_points", 20) or 20)),
            enforce_fail_closed=bool(raw.get("enforce_fail_closed", True)),
            quality_green_min=float(raw.get("quality_green_min", 80.0) or 80.0),
            quality_amber_min=float(raw.get("quality_amber_min", 55.0) or 55.0),
            amber_var_limit_multiplier=float(raw.get("amber_var_limit_multiplier", 0.85) or 0.85),
            amber_total_open_risk_multiplier=float(raw.get("amber_total_open_risk_multiplier", 0.9) or 0.9),
            red_var_limit_multiplier=float(raw.get("red_var_limit_multiplier", 0.7) or 0.7),
            red_total_open_risk_multiplier=float(raw.get("red_total_open_risk_multiplier", 0.8) or 0.8),
            scenario_shocks={
                str(k).strip().lower(): float(v)
                for k, v in dict(raw.get("scenario_shocks", {"base": 0.03, "volatile": 0.06})).items()
            },
            scenario_tail_percentile=float(raw.get("scenario_tail_percentile", 0.02) or 0.02),
        )

    def evaluate_proposed_trade(
        self,
        *,
        symbol: str,
        proposed_risk: float,
        open_risk_by_symbol: dict[str, float],
    ) -> tuple[bool, str, PortfolioVaRSnapshot]:
        pre_trade_total_open_risk = sum(max(0.0, float(v or 0.0)) for v in dict(open_risk_by_symbol).values())
        exposures = self._build_exposures(symbol=symbol, proposed_risk=proposed_risk, current=open_risk_by_symbol)
        total_open_risk = sum(exposures.values())
        symbols = list(exposures.keys())
        quality_score = 0.0
        quality_band = "red"
        effective_max_var_usd = float(self.config.max_var_usd)
        effective_max_total_open_risk = float(self.config.max_total_open_risk)

        if total_open_risk > effective_max_total_open_risk:
            pre_drawdown_pct = self._projected_drawdown_pct(pre_trade_total_open_risk, effective_max_total_open_risk)
            post_drawdown_pct = self._projected_drawdown_pct(total_open_risk, effective_max_total_open_risk)
            snapshot = self._snapshot(
                var_usd=0.0,
                total_open_risk=total_open_risk,
                data_points=0,
                quality_score=quality_score,
                quality_band=quality_band,
                effective_max_var_usd=effective_max_var_usd,
                effective_max_total_open_risk=effective_max_total_open_risk,
                breached=True,
                reason=(f"MAX TOTAL OPEN RISK exceeded: {total_open_risk:.2f} > {effective_max_total_open_risk:.2f}"),
                symbols=symbols,
                correlation_matrix={},
                projected_drawdown_pre_pct=pre_drawdown_pct,
                projected_drawdown_post_pct=post_drawdown_pct,
            )
            self._record_observability(snapshot)
            return False, snapshot.reason, snapshot

        returns_df = self._returns_frame(exposures)
        data_points = int(0 if returns_df is None else len(returns_df))
        quality_score = self._quality_score(data_points)
        quality_band = self._quality_band(quality_score)
        effective_max_var_usd, effective_max_total_open_risk = self._effective_limits(quality_band)

        if total_open_risk > effective_max_total_open_risk:
            reason = (
                f"MAX TOTAL OPEN RISK exceeded (quality={quality_band}): "
                f"{total_open_risk:.2f} > {effective_max_total_open_risk:.2f}"
            )
            pre_drawdown_pct = self._projected_drawdown_pct(pre_trade_total_open_risk, effective_max_total_open_risk)
            post_drawdown_pct = self._projected_drawdown_pct(total_open_risk, effective_max_total_open_risk)
            snapshot = self._snapshot(
                var_usd=0.0,
                total_open_risk=total_open_risk,
                data_points=data_points,
                quality_score=quality_score,
                quality_band=quality_band,
                effective_max_var_usd=effective_max_var_usd,
                effective_max_total_open_risk=effective_max_total_open_risk,
                breached=True,
                reason=reason,
                symbols=symbols,
                correlation_matrix={},
                projected_drawdown_pre_pct=pre_drawdown_pct,
                projected_drawdown_post_pct=post_drawdown_pct,
            )
            self._record_observability(snapshot)
            return False, reason, snapshot

        if returns_df is None or returns_df.empty or data_points < self.config.min_points:
            reason = f"Portfolio VaR unavailable: insufficient bar history ({data_points} < {self.config.min_points})"
            pre_drawdown_pct = self._projected_drawdown_pct(pre_trade_total_open_risk, effective_max_total_open_risk)
            post_drawdown_pct = self._projected_drawdown_pct(total_open_risk, effective_max_total_open_risk)
            snapshot = self._snapshot(
                var_usd=0.0,
                total_open_risk=total_open_risk,
                data_points=data_points,
                quality_score=quality_score,
                quality_band=quality_band,
                effective_max_var_usd=effective_max_var_usd,
                effective_max_total_open_risk=effective_max_total_open_risk,
                breached=self.config.enforce_fail_closed,
                reason=reason,
                symbols=symbols,
                correlation_matrix={},
                projected_drawdown_pre_pct=pre_drawdown_pct,
                projected_drawdown_post_pct=post_drawdown_pct,
            )
            self._record_observability(snapshot)
            if self.config.enforce_fail_closed:
                return False, reason, snapshot
            return True, "OK (portfolio VaR skipped: insufficient data)", snapshot

        corr = returns_df.corr().fillna(0.0)
        corr_dict = {
            str(row): {str(col): float(val) for col, val in row_vals.items()}
            for row, row_vals in corr.round(4).to_dict().items()
        }
        pnl_series = self._portfolio_pnl_series(exposures=exposures, returns_df=returns_df)
        var_usd = self._calculate_var_usd(pnl_series, exposures=exposures, returns_df=returns_df)
        breached = var_usd > effective_max_var_usd
        reason = (
            f"PORTFOLIO VAR breached ({quality_band}): {var_usd:.2f} > {effective_max_var_usd:.2f}"
            if breached
            else "OK"
        )
        pre_drawdown_pct = self._projected_drawdown_pct(pre_trade_total_open_risk, effective_max_total_open_risk)
        post_drawdown_pct = self._projected_drawdown_pct(total_open_risk, effective_max_total_open_risk)
        snapshot = self._snapshot(
            var_usd=var_usd,
            total_open_risk=total_open_risk,
            data_points=data_points,
            quality_score=quality_score,
            quality_band=quality_band,
            effective_max_var_usd=effective_max_var_usd,
            effective_max_total_open_risk=effective_max_total_open_risk,
            breached=breached,
            reason=reason,
            symbols=symbols,
            correlation_matrix=corr_dict,
            projected_drawdown_pre_pct=pre_drawdown_pct,
            projected_drawdown_post_pct=post_drawdown_pct,
        )
        self._record_observability(snapshot)
        return (not breached), reason, snapshot

    def _build_exposures(
        self,
        *,
        symbol: str,
        proposed_risk: float,
        current: dict[str, float],
    ) -> dict[str, float]:
        exposures = {str(k).strip().upper(): max(0.0, float(v or 0.0)) for k, v in dict(current).items()}
        key = str(symbol).strip().upper()
        exposures[key] = max(0.0, exposures.get(key, 0.0) + float(proposed_risk or 0.0))
        return {k: v for k, v in exposures.items() if v > 0.0}

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
        return PortfolioVaRSnapshot(
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
