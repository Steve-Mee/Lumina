from __future__ import annotations

import hashlib
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from .dna_registry import PolicyDNA


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

    def __init__(self, *, max_workers: int = 8, drawdown_limit_ratio: float = 0.02) -> None:
        self.max_workers = max(1, int(max_workers))
        self.drawdown_limit_ratio = max(0.0, float(drawdown_limit_ratio))

    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict[str, Any] | None = None,
        shadow_mode: bool = False,
    ) -> list[SimResult]:
        if not variants:
            return []

        report = dict(nightly_report or {})
        day_count = max(1, int(days))
        results: list[SimResult] = []

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(variants))) as pool:
            future_map = {
                pool.submit(self._evaluate_single_variant, variant, day_count, report, bool(shadow_mode)): variant
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
    ) -> SimResult:
        seed = _stable_seed(
            variant.hash,
            str(days),
            "shadow" if shadow_mode else "regular",
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
