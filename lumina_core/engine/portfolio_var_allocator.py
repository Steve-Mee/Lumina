from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


from lumina_core.engine.portfolio_var_calc import PortfolioVaRCalcMixin  # noqa: E402

class PortfolioVaRAllocator(PortfolioVaRCalcMixin):
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

