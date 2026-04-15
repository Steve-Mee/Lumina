from __future__ import annotations

from dataclasses import dataclass
from collections import deque

import pandas as pd

from lumina_core.engine.portfolio_var_allocator import PortfolioVaRAllocator
from lumina_core.engine.valuation_engine import ValuationEngine


@dataclass
class _StubMarketData:
    ohlc: pd.DataFrame

    def copy_ohlc(self) -> pd.DataFrame:
        return self.ohlc.copy()


@dataclass
class _StubNode:
    market_data: _StubMarketData
    prices_rolling: deque


@dataclass
class _StubSwarm:
    nodes: dict[str, _StubNode]


def _build_close_df(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(values), freq="1min"),
            "open": values,
            "high": values,
            "low": values,
            "close": values,
            "volume": [1000.0] * len(values),
        }
    )


def test_portfolio_var_blocks_on_correlated_spike() -> None:
    mes = [5000.0 + i * 0.5 for i in range(60)]
    nq = [17000.0 + i * 1.1 for i in range(60)]
    # Add synchronized shock to maximize correlation and tail loss.
    for idx in range(54, 60):
        mes[idx] = mes[idx - 1] - 40.0
        nq[idx] = nq[idx - 1] - 90.0

    swarm = _StubSwarm(
        nodes={
            "MES JUN26": _StubNode(market_data=_StubMarketData(_build_close_df(mes)), prices_rolling=deque(mes, maxlen=60)),
            "NQ JUN26": _StubNode(market_data=_StubMarketData(_build_close_df(nq)), prices_rolling=deque(nq, maxlen=60)),
        }
    )

    allocator = PortfolioVaRAllocator(
        valuation_engine=ValuationEngine(),
        swarm_manager=swarm,
        config={
            "confidence": 0.95,
            "window_days": 30,
            "max_var_usd": 50.0,
            "max_total_open_risk": 4000.0,
            "method": "historical",
            "min_points": 20,
        },
    )

    allowed, reason, snapshot = allocator.evaluate_proposed_trade(
        symbol="MES JUN26",
        proposed_risk=600.0,
        open_risk_by_symbol={"MES JUN26": 900.0, "NQ JUN26": 900.0},
    )

    assert allowed is False
    assert "PORTFOLIO VAR breached" in reason
    assert snapshot.breached is True
    assert snapshot.var_usd > snapshot.max_var_usd
    assert "MES JUN26" in snapshot.correlation_matrix
    assert snapshot.quality_band in {"green", "amber", "red"}
    assert snapshot.effective_max_var_usd <= snapshot.max_var_usd


def test_portfolio_var_respects_total_open_risk_cap() -> None:
    prices = [5000.0 + i * 0.2 for i in range(40)]
    swarm = _StubSwarm(
        nodes={
            "MES JUN26": _StubNode(market_data=_StubMarketData(_build_close_df(prices)), prices_rolling=deque(prices, maxlen=60)),
        }
    )

    allocator = PortfolioVaRAllocator(
        valuation_engine=ValuationEngine(),
        swarm_manager=swarm,
        config={
            "max_var_usd": 1200.0,
            "max_total_open_risk": 1000.0,
            "min_points": 20,
        },
    )

    allowed, reason, snapshot = allocator.evaluate_proposed_trade(
        symbol="MES JUN26",
        proposed_risk=500.0,
        open_risk_by_symbol={"MES JUN26": 700.0},
    )

    assert allowed is False
    assert "MAX TOTAL OPEN RISK exceeded" in reason
    assert snapshot.total_open_risk > snapshot.effective_max_total_open_risk


def test_portfolio_var_prefers_max_portfolio_var_usd_key() -> None:
    prices = [5000.0 + i * 0.3 for i in range(40)]
    swarm = _StubSwarm(
        nodes={
            "MES JUN26": _StubNode(market_data=_StubMarketData(_build_close_df(prices)), prices_rolling=deque(prices, maxlen=60)),
        }
    )

    allocator = PortfolioVaRAllocator(
        valuation_engine=ValuationEngine(),
        swarm_manager=swarm,
        config={
            "max_portfolio_var_usd": 321.0,
            "max_var_usd": 999.0,
            "min_points": 20,
        },
    )

    assert allocator.config.max_var_usd == 321.0
