from __future__ import annotations

import hashlib
import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import pandas as pd

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
        true_backtest_mode: bool = False,
        market_data_service: Any | None = None,
    ) -> None:
        self.max_workers = max(1, int(max_workers))
        self.drawdown_limit_ratio = max(0.0, float(drawdown_limit_ratio))
        self.real_market_data = bool(real_market_data)
        self.true_backtest_mode = bool(true_backtest_mode)
        self.market_data_service = market_data_service

    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict[str, Any] | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
        true_backtest_mode: bool = False,
    ) -> list[SimResult]:
        if not variants:
            return []

        report = dict(nightly_report or {})
        day_count = max(1, int(days))
        use_real_data = bool(real_market_data) and self.real_market_data and self.market_data_service is not None
        use_true_backtest = bool(true_backtest_mode) and self.true_backtest_mode and use_real_data
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
                    use_true_backtest,
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
        true_backtest_mode: bool = False,
    ) -> SimResult:
        seed = _stable_seed(
            variant.hash,
            str(days),
            "shadow" if shadow_mode else "regular",
            "real_data" if real_market_data else "simulated",
            "true_backtest" if true_backtest_mode else "heuristic_backtest",
            json.dumps(report, sort_keys=True, ensure_ascii=True),
        )
        rng = random.Random(seed)

        base_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        base_sharpe = float(report.get("sharpe", 0.0) or 0.0)
        base_drawdown_abs = abs(float(report.get("max_drawdown", 0.0) or 0.0))
        baseline_equity = max(1.0, float(report.get("account_equity", 50000.0) or 50000.0))

        pnl_values: list[float] = []
        regime_fit_bonus = 0.0
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

        if true_backtest_mode and real_market_data and real_ticks:
            backtest = self._run_true_backtest(
                ticks=real_ticks,
                target_days=days,
                baseline_equity=baseline_equity,
                variant=variant,
                rng=rng,
                shadow_mode=shadow_mode,
            )
            pnl_values = list(backtest.get("daily_pnl", []) or [])
            max_drawdown_ratio = float(backtest.get("max_drawdown_ratio", 0.0) or 0.0)
            regime_fit_bonus = float(backtest.get("regime_fit_bonus", 0.0) or 0.0)
            if shadow_mode:
                hypothetical_fills = list(backtest.get("fills", []) or [])
        elif real_market_data and real_ticks:
            # Use real tick data to calculate PnL
            pnl_values = self._calculate_real_pnl(real_ticks, days, baseline_equity, variant, rng)
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
        if not true_backtest_mode:
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

    def _run_true_backtest(
        self,
        *,
        ticks: list[dict[str, Any]],
        target_days: int,
        baseline_equity: float,
        variant: PolicyDNA,
        rng: random.Random,
        shadow_mode: bool,
    ) -> dict[str, Any]:
        daily_bars = self._group_ticks_by_day(ticks=ticks)
        day_keys = sorted(daily_bars.keys())[-max(1, int(target_days)) :]

        equity = float(baseline_equity)
        peak_equity = float(baseline_equity)
        max_dd_ratio = 0.0
        regime_bonus = 0.0
        fills: list[ShadowFill] = []
        pnl_values: list[float] = []

        variant_focus = self._variant_regime_focus(variant)

        for idx, day_key in enumerate(day_keys, start=1):
            day_ticks = daily_bars.get(day_key, [])
            if len(day_ticks) < 2:
                pnl_values.append(0.0)
                continue

            day_df = self._ticks_to_ohlc_frame(day_ticks)
            day_regime = self._detect_day_regime(day_df=day_df)
            regime_bonus += self._regime_alignment_score(variant_focus=variant_focus, detected_regime=day_regime)

            trade = self._simulate_day_trade(
                day_ticks=day_ticks,
                variant=variant,
                variant_focus=variant_focus,
                detected_regime=day_regime,
                rng=rng,
            )
            day_pnl = float(trade.get("pnl", 0.0) or 0.0)
            pnl_values.append(day_pnl)

            equity += day_pnl
            peak_equity = max(peak_equity, equity)
            drawdown = max(0.0, peak_equity - equity)
            max_dd_ratio = max(max_dd_ratio, drawdown / max(1.0, baseline_equity))

            if shadow_mode:
                fills.append(
                    ShadowFill(
                        day_index=idx,
                        side=str(trade.get("side", "HOLD")),
                        qty=int(trade.get("qty", 1) or 1),
                        entry_price=float(trade.get("entry_price", 0.0) or 0.0),
                        exit_price=float(trade.get("exit_price", 0.0) or 0.0),
                        pnl=day_pnl,
                        reason=f"shadow_true_backtest_{day_regime.lower()}",
                    )
                )

        normalized_regime_bonus = max(-0.75, min(0.75, regime_bonus / max(1, len(day_keys))))
        return {
            "daily_pnl": pnl_values,
            "max_drawdown_ratio": max_dd_ratio,
            "regime_fit_bonus": normalized_regime_bonus,
            "fills": fills,
        }

    @staticmethod
    def _group_ticks_by_day(*, ticks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tick in ticks:
            ts = str(tick.get("timestamp", "") or "")
            if len(ts) < 10:
                continue
            day_key = ts[:10]
            grouped.setdefault(day_key, []).append(tick)
        return grouped

    def _variant_regime_focus(self, variant: PolicyDNA) -> str:
        raw_content = str(getattr(variant, "content", "") or "")
        payload: dict[str, Any] = {}
        try:
            loaded = json.loads(raw_content)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}

        explicit = str(payload.get("regime_focus", "") or "").strip().lower()
        if explicit:
            return explicit
        text = raw_content.lower()
        if "trend" in text:
            return "trending"
        if "range" in text:
            return "ranging"
        if "volatility" in text or "volatile" in text:
            return "high_volatility"
        return "neutral"

    def _ticks_to_ohlc_frame(self, day_ticks: list[dict[str, Any]]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for tick in day_ticks:
            px = float(tick.get("last", 0.0) or 0.0)
            if px <= 0.0:
                continue
            rows.append(
                {
                    "timestamp": tick.get("timestamp"),
                    "open": px,
                    "high": float(tick.get("high", px) or px),
                    "low": float(tick.get("low", px) or px),
                    "close": px,
                    "volume": float(tick.get("volume", 0.0) or 0.0),
                }
            )
        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(rows)

    def _detect_day_regime(self, *, day_df: pd.DataFrame) -> str:
        engine = getattr(self.market_data_service, "engine", None)
        if engine is not None and hasattr(engine, "detect_market_regime") and len(day_df) > 4:
            try:
                regime = engine.detect_market_regime(day_df)
                return str(regime or "NEUTRAL").upper()
            except Exception:
                pass
        return "NEUTRAL"

    @staticmethod
    def _regime_alignment_score(*, variant_focus: str, detected_regime: str) -> float:
        focus = str(variant_focus or "neutral").lower()
        regime = str(detected_regime or "NEUTRAL").lower()
        if focus == "neutral":
            return 0.02
        if ("trend" in focus and "trend" in regime) or ("range" in focus and "rang" in regime):
            return 0.12
        if "vol" in focus and ("vol" in regime or "news" in regime):
            return 0.12
        return -0.06

    def _simulate_day_trade(
        self,
        *,
        day_ticks: list[dict[str, Any]],
        variant: PolicyDNA,
        variant_focus: str,
        detected_regime: str,
        rng: random.Random,
    ) -> dict[str, Any]:
        first = day_ticks[0]
        last = day_ticks[-1]
        open_px = float(first.get("last", 0.0) or 0.0)
        close_px = float(last.get("last", open_px) or open_px)
        highs = [float(t.get("last", open_px) or open_px) for t in day_ticks]
        day_high = max(highs) if highs else open_px
        day_low = min(highs) if highs else open_px
        day_range = max(0.25, day_high - day_low)

        focus = str(variant_focus or "neutral").lower()
        regime = str(detected_regime or "NEUTRAL").lower()
        trend_up = close_px >= open_px
        if "range" in focus:
            side = -1 if trend_up else 1
        elif "trend" in focus or "trend" in regime:
            side = 1 if trend_up else -1
        elif "vol" in focus:
            side = 1 if rng.random() >= 0.5 else -1
        else:
            side = 1 if trend_up else -1

        qty = max(1, min(3, int(1 + round(float(getattr(variant, "mutation_rate", 0.0) or 0.0) * 4.0))))
        stop_distance = max(0.25, day_range * 0.35)
        target_distance = max(0.25, day_range * 0.60)

        entry_price = float(first.get("ask", open_px) if side > 0 else first.get("bid", open_px))
        stop_price = entry_price - stop_distance if side > 0 else entry_price + stop_distance
        target_price = entry_price + target_distance if side > 0 else entry_price - target_distance

        exit_price = close_px
        for tick in day_ticks[1:]:
            bid = float(tick.get("bid", tick.get("last", close_px)) or close_px)
            ask = float(tick.get("ask", tick.get("last", close_px)) or close_px)
            mark = bid if side > 0 else ask
            if side > 0 and mark <= stop_price:
                exit_price = stop_price
                break
            if side > 0 and mark >= target_price:
                exit_price = target_price
                break
            if side < 0 and mark >= stop_price:
                exit_price = stop_price
                break
            if side < 0 and mark <= target_price:
                exit_price = target_price
                break

        point_value = self._point_value()
        pnl = (exit_price - entry_price) * float(side) * float(qty) * float(point_value)
        commission = self._commission_cost(qty=qty)
        net_pnl = float(pnl - commission)

        return {
            "side": "BUY" if side > 0 else "SELL",
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": net_pnl,
        }

    def _point_value(self) -> float:
        engine = getattr(self.market_data_service, "engine", None)
        valuation = getattr(engine, "valuation_engine", None)
        instrument = str(getattr(getattr(engine, "config", None), "instrument", "MES") or "MES")
        if valuation is not None and hasattr(valuation, "point_value"):
            try:
                return float(valuation.point_value(instrument))
            except Exception:
                return 5.0
        return 5.0

    def _commission_cost(self, *, qty: int) -> float:
        engine = getattr(self.market_data_service, "engine", None)
        valuation = getattr(engine, "valuation_engine", None)
        instrument = str(getattr(getattr(engine, "config", None), "instrument", "MES") or "MES")
        if valuation is not None and hasattr(valuation, "commission_dollars"):
            try:
                return float(valuation.commission_dollars(symbol=instrument, quantity=int(qty), sides=2))
            except Exception:
                return float(qty) * 2.58
        return float(qty) * 2.58
