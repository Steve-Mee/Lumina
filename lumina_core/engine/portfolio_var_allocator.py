from __future__ import annotations

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
    breached: bool
    reason: str
    symbols: list[str]
    correlation_matrix: dict[str, dict[str, float]]


@dataclass(slots=True)
class PortfolioVaRConfig:
    confidence: float = 0.95
    window_days: int = 30
    max_var_usd: float = 1200.0
    max_total_open_risk: float = 3000.0
    method: str = "historical"
    min_points: int = 20
    enforce_fail_closed: bool = True


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
        )

    def evaluate_proposed_trade(
        self,
        *,
        symbol: str,
        proposed_risk: float,
        open_risk_by_symbol: dict[str, float],
    ) -> tuple[bool, str, PortfolioVaRSnapshot]:
        exposures = self._build_exposures(symbol=symbol, proposed_risk=proposed_risk, current=open_risk_by_symbol)
        total_open_risk = sum(exposures.values())
        symbols = list(exposures.keys())

        if total_open_risk > self.config.max_total_open_risk:
            snapshot = self._snapshot(
                var_usd=0.0,
                total_open_risk=total_open_risk,
                breached=True,
                reason=(
                    f"MAX TOTAL OPEN RISK exceeded: {total_open_risk:.2f} > "
                    f"{self.config.max_total_open_risk:.2f}"
                ),
                symbols=symbols,
                correlation_matrix={},
            )
            self._record_observability(snapshot)
            return False, snapshot.reason, snapshot

        returns_df = self._returns_frame(exposures)
        if returns_df is None or returns_df.empty or len(returns_df) < self.config.min_points:
            reason = (
                f"Portfolio VaR unavailable: insufficient bar history "
                f"({0 if returns_df is None else len(returns_df)} < {self.config.min_points})"
            )
            snapshot = self._snapshot(
                var_usd=0.0,
                total_open_risk=total_open_risk,
                breached=self.config.enforce_fail_closed,
                reason=reason,
                symbols=symbols,
                correlation_matrix={},
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
        var_usd = self._calculate_var_usd(pnl_series)
        breached = var_usd > self.config.max_var_usd
        reason = (
            f"PORTFOLIO VAR breached: {var_usd:.2f} > {self.config.max_var_usd:.2f}"
            if breached
            else "OK"
        )
        snapshot = self._snapshot(
            var_usd=var_usd,
            total_open_risk=total_open_risk,
            breached=breached,
            reason=reason,
            symbols=symbols,
            correlation_matrix=corr_dict,
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

    def _calculate_var_usd(self, pnl_series: pd.Series) -> float:
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

        # Default method: historical VaR
        return max(0.0, float(losses.quantile(confidence)))

    def _snapshot(
        self,
        *,
        var_usd: float,
        total_open_risk: float,
        breached: bool,
        reason: str,
        symbols: list[str],
        correlation_matrix: dict[str, dict[str, float]],
    ) -> PortfolioVaRSnapshot:
        return PortfolioVaRSnapshot(
            var_usd=float(var_usd),
            max_var_usd=float(self.config.max_var_usd),
            total_open_risk=float(total_open_risk),
            max_total_open_risk=float(self.config.max_total_open_risk),
            confidence=float(self.config.confidence),
            window_days=int(self.config.window_days),
            method=str(self.config.method),
            breached=bool(breached),
            reason=str(reason),
            symbols=list(symbols),
            correlation_matrix=correlation_matrix,
        )

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
            return
