"""Variant evaluation entrypoints for MultiDaySimRunner."""
from __future__ import annotations

import json
import logging
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


from .bot_stress_choices import resolve_ohlc_reality_stress_enabled
from .dna_registry import PolicyDNA
from .reality_generator import build_parallel_reports, stress_simulator_ohlc
from .multi_day_sim_types import ShadowFill, SimResult, stable_seed as _stable_seed

logger = logging.getLogger(__name__)

class MultiDaySimEvaluateMixin:
    """evaluate_variants + single-variant orchestration."""

    """Runs parallel multi-day SIM evaluations for DNA variants."""

    def evaluate_variants(
        self,
        variants: list[PolicyDNA],
        *,
        days: int,
        nightly_report: dict[str, Any] | None = None,
        shadow_mode: bool = False,
        real_market_data: bool = False,
        true_backtest_mode: bool = False,
        parallel_realities: int = 1,
    ) -> list[SimResult]:
        if not variants:
            return []

        report = dict(nightly_report or {})
        day_count = max(1, int(days))
        use_real_data = bool(real_market_data) and self.real_market_data and self.market_data_service is not None
        use_true_backtest = bool(true_backtest_mode) and self.true_backtest_mode and use_real_data
        results: list[SimResult] = []

        eff_parallel = 1 if bool(shadow_mode) else max(1, min(50, int(parallel_realities)))

        if eff_parallel < 2:
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
                        logging.exception(
                            "Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:107"
                        )
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
        else:
            reports = build_parallel_reports(
                report,
                eff_parallel,
                seed=json.dumps(report, sort_keys=True, ensure_ascii=True),
            )
            jobs = [(variant, rep) for variant in variants for rep in reports]
            max_workers = min(32, max(self.max_workers, len(jobs)))
            buckets: dict[str, list[SimResult]] = defaultdict(list)

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                future_map = {
                    pool.submit(
                        self._evaluate_single_variant,
                        variant,
                        day_count,
                        rep,
                        bool(shadow_mode),
                        use_real_data,
                        use_true_backtest,
                    ): variant
                    for variant, rep in jobs
                }
                for future in as_completed(future_map):
                    variant = future_map[future]
                    try:
                        buckets[variant.hash].append(future.result())
                    except Exception:
                        logging.exception(
                            "Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:147"
                        )
                        buckets[variant.hash].append(
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

            for variant in variants:
                parts = buckets.get(variant.hash, [])
                results.append(self._aggregate_multi_reality(parts, variant=variant, day_count=day_count))

        results.sort(key=lambda item: item.fitness, reverse=True)
        return results

    @staticmethod
    def _aggregate_multi_reality(
        parts: list[SimResult],
        *,
        variant: PolicyDNA,
        day_count: int,
    ) -> SimResult:
        """Worst-universe aggregation: min fitness / PnL bonus, max drawdown."""
        if not parts:
            return SimResult(
                dna_hash=variant.hash,
                day_count=day_count,
                avg_pnl=0.0,
                max_drawdown_ratio=1.0,
                regime_fit_bonus=0.0,
                fitness=float("-inf"),
                shadow_mode=False,
                hypothetical_fills=None,
            )
        worst_fitness = min(r.fitness for r in parts)
        tie = next(r for r in parts if r.fitness == worst_fitness)
        return SimResult(
            dna_hash=variant.hash,
            day_count=day_count,
            avg_pnl=min(r.avg_pnl for r in parts),
            max_drawdown_ratio=max(r.max_drawdown_ratio for r in parts),
            regime_fit_bonus=min(r.regime_fit_bonus for r in parts),
            fitness=worst_fitness,
            shadow_mode=tie.shadow_mode,
            hypothetical_fills=tie.hypothetical_fills,
        )

    def _test_generated_strategy(self, code_snippet: str) -> float:
        """Fail-closed helper: validate generated code and score via backtest path."""
        try:
            from .strategy_generator import StrategyGenerator

            sandbox = StrategyGenerator().compile_and_validate(code_snippet)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:206")
            return float("-inf")

        metadata = dict(sandbox.metadata)
        content_payload = {
            "strategy_type": "generated",
            "generated_entrypoint": sandbox.function_name,
            "generated_code": sandbox.code,
            "regime_focus": str(metadata.get("regime_focus", "neutral") or "neutral"),
            "signal_bias": str(metadata.get("signal_bias", "neutral") or "neutral"),
            "confidence": float(metadata.get("confidence", 0.0) or 0.0),
            "name": str(metadata.get("name", "generated_strategy") or "generated_strategy"),
        }
        candidate = PolicyDNA.create(
            prompt_id="self_generated_strategy",
            version="generated_candidate",
            content=content_payload,
            fitness_score=0.0,
            generation=0,
            mutation_rate=0.10,
            lineage_hash="GENERATOR",
        )

        results = self.evaluate_variants(
            [candidate],
            days=7,
            nightly_report={
                "net_pnl": 200.0,
                "sharpe": 0.8,
                "max_drawdown": 120.0,
                "account_equity": 50000.0,
            },
            real_market_data=True,
            true_backtest_mode=True,
        )
        if not results:
            return float("-inf")
        return float(results[0].fitness)

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

        if resolve_ohlc_reality_stress_enabled() and real_ticks and report.get("_reality_id") is not None:
            real_ticks = stress_simulator_ohlc(
                real_ticks,
                int(report.get("_reality_id", 0) or 0),
                stress_seed=str(variant.hash),
            )

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
            from lumina_core.hybrid_quarantine import (
                MULTI_DAY_SIM,
                log_quarantine,
                require_true_backtest,
            )

            strict = require_true_backtest()
            log_quarantine(MULTI_DAY_SIM, strict=strict, detail="tick_proxy_path")
            if strict:
                return SimResult(
                    dna_hash=variant.hash,
                    day_count=days,
                    avg_pnl=0.0,
                    max_drawdown_ratio=0.0,
                    regime_fit_bonus=0.0,
                    fitness=float("-inf"),
                    shadow_mode=shadow_mode,
                    hypothetical_fills=None,
                )
            # Tick-bar proxy daily PnL (not broker economic_pnl)
            pnl_values = self._calculate_tick_proxy_daily_pnl(real_ticks, days, baseline_equity, variant, rng)
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
            from lumina_core.hybrid_quarantine import (
                MULTI_DAY_SIM,
                log_quarantine,
                require_true_backtest,
            )

            strict = require_true_backtest()
            log_quarantine(MULTI_DAY_SIM, strict=strict, detail="rng_heuristic_path")
            if strict:
                return SimResult(
                    dna_hash=variant.hash,
                    day_count=days,
                    avg_pnl=0.0,
                    max_drawdown_ratio=0.0,
                    regime_fit_bonus=0.0,
                    fitness=float("-inf"),
                    shadow_mode=shadow_mode,
                    hypothetical_fills=None,
                )
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
        de = report.get("dream_engine")
        if isinstance(de, dict) and de:
            from .dream_engine import dream_policy_alignment_bonus

            fitness += dream_policy_alignment_bonus(variant.content, de)

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

