from __future__ import annotations

import hashlib
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .dna_registry import PolicyDNA

logger = logging.getLogger(__name__)


def _stable_seed(*parts: str) -> int:
    payload = "|".join(parts)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)


@dataclass(slots=True)
class ShadowFill:
    day_index: int
    side: str
    qty: int
    entry_price: float
    exit_price: float
    pnl: float
    reason: str


@dataclass(slots=True)
class SimResult:
    dna_hash: str
    day_count: int
    avg_pnl: float
    max_drawdown_ratio: float
    regime_fit_bonus: float
    fitness: float
    shadow_mode: bool = False
    hypothetical_fills: list[ShadowFill] | None = None


class MultiDaySimRunner:
    """Runs parallel multi-day SIM evaluations for DNA variants."""

    def __init__(
        self,
        *,
        max_workers: int = 8,
        drawdown_limit_ratio: float = 0.02,
        real_market_data: bool = False,
        market_data_service: Any | None = None,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.drawdown_limit_ratio = max(0.0, float(drawdown_limit_ratio))
        self.real_market_data = bool(real_market_data)
        self.market_data_service = market_data_service

    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict[str, Any] | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
    ) -> list[SimResult]:
        if not variants:
            return []

        report = dict(nightly_report or {})
        day_count = max(1, int(days))
        use_real_data = bool(real_market_data) and self.real_market_data and self.market_data_service is not None
        results: list[SimResult] = []

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(variants))) as pool:
            future_map = {
                pool.submit(
                    self._evaluate_single_variant,
                    variant,
                    day_count,
                    report,
                    bool(shadow_mode),
                    use_real_data,
                ): variant
                for variant in variants
            }
            for future in as_completed(future_map):
                variant = future_map[future]
                try:
                    results.append(future.result())
                except Exception:
                    results.append(
                        SimResult(
                            dna_hash=variant.hash,
                            day_count=day_count,
                            avg_pnl=0.0,
                            max_drawdown_ratio=1.0,
                            regime_fit_bonus=0.0,
                            fitness=float("-inf"),
                            shadow_mode=bool(shadow_mode),
                            hypothetical_fills=[] if shadow_mode else None,
                        )
                    )

        results.sort(key=lambda item: item.fitness, reverse=True)
        return results

    def _evaluate_single_variant(
        self,
        variant: PolicyDNA,
        days: int,
        report: dict[str, Any],
        shadow_mode: bool,
        real_market_data: bool = False,
    ) -> SimResult:
        seed = _stable_seed(
            variant.hash,
            str(days),
            "shadow" if shadow_mode else "regular",
            "real_data" if real_market_data else "simulated",
            json.dumps(report, sort_keys=True, ensure_ascii=True),
        )
        rng = random.Random(seed)

        base_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        base_sharpe = float(report.get("sharpe", 0.0) or 0.0)
        base_drawdown_abs = abs(float(report.get("max_drawdown", 0.0) or 0.0))
        baseline_equity = max(1.0, float(report.get("account_equity", 50000.0) or 50000.0))

        pnl_values: list[float] = []
        max_drawdown_ratio = 0.0
        hypothetical_fills: list[ShadowFill] = []

        # FASE 1: Load real market data if enabled
        real_ticks: list[dict[str, Any]] = []
        if real_market_data and self.market_data_service is not None:
            try:
                days_back = max(7, days // 5)  # Fetch extra historical context
                real_ticks = self.market_data_service.load_historical_ohlc_extended(
                    days_back=days_back,
                    limit=max(5000, days * 250),
                    ticks_per_bar=4,
                )
                if not real_ticks:
                    logger.warning("[EVOLUTION] No real market data available, falling back to simulation")
                    real_market_data = False
            except Exception as exc:
                logger.warning("[EVOLUTION] Real market data load failed: %s – using simulation", exc)
                real_market_data = False

        if real_market_data and real_ticks:
            # Use real tick data to calculate PnL
            pnl_values = self._calculate_real_pnl(
                real_ticks, days, baseline_equity, variant, rng
            )
            for day_idx, day_pnl in enumerate(pnl_values):
                day_dd_ratio = max(0.0, base_drawdown_abs * (1.0 + rng.uniform(-0.1, 0.1)) / baseline_equity)
                max_drawdown_ratio = max(max_drawdown_ratio, day_dd_ratio)

                if shadow_mode:
                    side = "BUY" if day_pnl >= 0.0 else "SELL"
                    qty = max(1, int(abs(day_pnl) // 50) + 1)
                    entry_price = 100.0
                    exit_price = entry_price + (day_pnl / max(1, qty * 10.0))
                    hypothetical_fills.append(
                        ShadowFill(
                            day_index=day_idx + 1,
                            side=side,
                            qty=qty,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pnl=float(day_pnl),
                            reason="shadow_real_market_validation",
                        )
                    )
        else:
            # Original random perturbation logic (backwards compatible)
            for day_index in range(1, days + 1):
                day_pnl = base_pnl * (1.0 + rng.uniform(-0.2, 0.2))
                day_dd_abs = base_drawdown_abs * (1.0 + rng.uniform(-0.15, 0.15))
                day_dd_ratio = max(0.0, day_dd_abs / baseline_equity)
                pnl_values.append(day_pnl)
                max_drawdown_ratio = max(max_drawdown_ratio, day_dd_ratio)

                if shadow_mode:
                    side = "BUY" if day_pnl >= 0.0 else "SELL"
                    qty = max(1, int(abs(day_pnl) // 25) + 1)
                    entry_price = round(100.0 + rng.uniform(-3.0, 3.0), 4)
                    exit_price = round(entry_price + (day_pnl / max(1, qty * 10.0)), 4)
                    hypothetical_fills.append(
                        ShadowFill(
                            day_index=day_index,
                            side=side,
                            qty=qty,
                            entry_price=entry_price,
                            exit_price=exit_price,
                            pnl=float(day_pnl),
                            reason="shadow_validation_no_order_execution",
                        )
                    )

        if max_drawdown_ratio > self.drawdown_limit_ratio:
            return SimResult(
                dna_hash=variant.hash,
                day_count=days,
                avg_pnl=float(sum(pnl_values) / len(pnl_values)) if pnl_values else 0.0,
                max_drawdown_ratio=max_drawdown_ratio,
                regime_fit_bonus=0.0,
                fitness=float("-inf"),
                shadow_mode=shadow_mode,
                hypothetical_fills=hypothetical_fills if shadow_mode else None,
            )

        avg_pnl = float(sum(pnl_values) / len(pnl_values)) if pnl_values else 0.0
        regime_fit_bonus = max(-0.5, min(0.5, base_sharpe * 0.1 + rng.uniform(-0.05, 0.05)))
        drawdown_penalty = max_drawdown_ratio * 100.0
        fitness = avg_pnl - drawdown_penalty + regime_fit_bonus

        return SimResult(
            dna_hash=variant.hash,
            day_count=days,
            avg_pnl=avg_pnl,
            max_drawdown_ratio=max_drawdown_ratio,
            regime_fit_bonus=regime_fit_bonus,
            fitness=fitness,
            shadow_mode=shadow_mode,
            hypothetical_fills=hypothetical_fills if shadow_mode else None,
        )

    def _calculate_real_pnl(
        self,
        ticks: list[dict[str, Any]],
        target_days: int,
        baseline_equity: float,
        variant: PolicyDNA,
        rng: random.Random,
    ) -> list[float]:
        """Calculate daily PnL from real tick data with variant-specific win rate."""
        pnl_values: list[float] = []
        if not ticks:
            return pnl_values

        # Group ticks by day
        ticks_by_day: dict[str, list[dict[str, Any]]] = {}
        for tick in ticks:
            try:
                ts_str = tick.get("timestamp", "")
                if not ts_str:
                    continue
                day_key = str(ts_str)[:10]  # YYYY-MM-DD
                if day_key not in ticks_by_day:
                    ticks_by_day[day_key] = []
                ticks_by_day[day_key].append(tick)
            except Exception:
                continue

        sorted_days = sorted(ticks_by_day.keys())[-target_days:]

        # Extract variant win_rate if available; otherwise use reasonable default
        variant_dict = getattr(variant, "__dict__", {}) if hasattr(variant, "__dict__") else {}
        variant_win_rate = float(variant_dict.get("win_rate", 0.52) or 0.52)
        variant_win_rate = max(0.45, min(0.65, variant_win_rate))  # Clamp to realistic range

        for day_key in sorted_days:
            day_ticks = ticks_by_day[day_key]
            if len(day_ticks) < 2:
                pnl_values.append(0.0)
                continue

            # Calculate intraday price moves and derive daily PnL
            entry_price = float(day_ticks[0].get("last", 100.0))
            exit_price = float(day_ticks[-1].get("last", entry_price))
            max_price = max(float(t.get("high", t.get("last", entry_price))) for t in day_ticks)
            min_price = min(float(t.get("low", t.get("last", entry_price))) for t in day_ticks)

            # Probabilistic win/loss based on variant win_rate
            is_win = rng.random() < variant_win_rate
            if is_win:
                # Wins: capture 40-60% of daily range
                range_pnl = (max_price - min_price) * rng.uniform(0.4, 0.6)
                daily_pnl = range_pnl * rng.uniform(0.9, 1.1)
            else:
                # Losses: lose 20-40% of daily range
                range_loss = (max_price - min_price) * rng.uniform(0.2, 0.4)
                daily_pnl = -range_loss * rng.uniform(0.9, 1.1)

            pnl_values.append(float(daily_pnl))

        return pnl_values
