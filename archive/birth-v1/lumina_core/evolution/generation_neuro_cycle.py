"""Neuroevolution cycle for EvolutionOrchestrator."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader

from .bot_stress_choices import resolve_neuro_ohlc_stress_rollouts
from .dna_registry import PolicyDNA
from .fitness_evaluator import (
    seed_from_hash as _seed_from_hash,
    utc_file_stamp as _utc_file_stamp,
)
from .meta_swarm import parallel_realities_from_config
from .neuroevolution import evaluate_weight_population
from .reality_generator import aggregate_ppo_eval_worst_reality, stress_simulator_ohlc
from .simulator_data_support import resolve_neuro_simulator_rows_for_neuro_cycle

logger = logging.getLogger(__name__)

class OrchestratorNeuroCycleMixin:
    """Weight-population neuroevolution cycle."""

    def _run_neuroevolution_cycle(
        self,
        *,
        generation_offset: int,
        mode: str,
        baseline_fitness: float,
        anchor_dna: PolicyDNA,
        nightly_report: dict[str, Any],
        sim_days: int,
    ) -> dict[str, Any]:
        _ = baseline_fitness  # DNA baseline; neuro promotion uses rollout_baseline from RL env only
        if str(mode).strip().lower() == "real":
            # Fail-closed: no autonomous weight mutation in REAL runtime.
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "real_mode_fail_closed"}

        ppo_trainer = self._resolve_ppo_trainer()
        if ppo_trainer is None:
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "ppo_trainer_unbound"}

        if not hasattr(ppo_trainer, "evaluate_policy_zip_rollouts"):
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "ppo_trainer_missing_rollout_eval"}

        engine = getattr(ppo_trainer, "engine", None)
        base_model = getattr(engine, "rl_policy_model", None)
        if base_model is None:
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "no_active_ppo_model"}

        cfg = ConfigLoader.section("evolution", "neuroevolution", default={})
        cfg = cfg if isinstance(cfg, dict) else {}
        simulator_data, neuro_data_source, strict_skip = resolve_neuro_simulator_rows_for_neuro_cycle(
            dict(nightly_report),
            engine=engine,
            neuro_cfg=cfg,
        )
        if strict_skip:
            logger.warning("[NEURO] skipped weight population: %s (source=%s)", strict_skip, neuro_data_source)
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": strict_skip,
                "neuro_simulator_data_source": neuro_data_source,
            }
        logger.info(
            "[NEURO] rollout data source=%s bars=%d",
            neuro_data_source,
            len(simulator_data),
        )
        pr_cfg = int(parallel_realities_from_config())
        stress_universa_enabled = bool(cfg.get("stress_universa_enabled", True))
        stress_universa_max = max(1, min(50, int(cfg.get("stress_universa_max", 12) or 12)))
        if not stress_universa_enabled:
            eff_neuro_stress = 1
        else:
            eff_neuro_stress = max(1, min(stress_universa_max, pr_cfg, 50))
        neuro_stress_seed = f"neuro:{anchor_dna.hash}:{generation_offset}"

        use_ohlc_stress_rollouts = bool(resolve_neuro_ohlc_stress_rollouts()) and eff_neuro_stress >= 2
        _neuro_meta = {
            "neuro_simulator_data_source": neuro_data_source,
            "neuro_stress_universa": eff_neuro_stress,
            "neuro_stress_universa_enabled": stress_universa_enabled,
            "neuro_ohlc_stress_rollouts": use_ohlc_stress_rollouts,
        }
        population_size = max(5, min(8, int(cfg.get("population_size", 6) or 6)))
        mutation_std = float(cfg.get("mutation_std", 0.01) or 0.01)
        mutation_rate = float(cfg.get("mutation_rate", 0.08) or 0.08)
        crossover_ratio = float(cfg.get("crossover_ratio", 0.5) or 0.5)
        shadow_max_steps = max(32, int(cfg.get("shadow_max_steps", 256) or 256))
        backtest_max_steps = max(256, int(cfg.get("backtest_max_steps", 2048) or 2048))
        backtest_max_steps = min(5000, max(backtest_max_steps, max(256, int(sim_days) * 120)))

        baseline_snapshot = self._neuro_weights_path / f"baseline_gen{generation_offset}_{_utc_file_stamp()}.zip"
        baseline_snapshot.parent.mkdir(parents=True, exist_ok=True)
        try:
            ppo_trainer.save_weights(baseline_snapshot)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/orchestrator_core.py:859")
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "baseline_save_failed",
                **_neuro_meta,
            }

        def _ppo_worst_across_ohlc_bars(
            policy_path: Path,
            raw_bars: list[dict[str, Any]],
        ) -> dict[str, Any]:
            if not use_ohlc_stress_rollouts:
                raise RuntimeError("ohlc rollouts not active")
            evals: list[dict[str, Any]] = []
            for i in range(int(eff_neuro_stress)):
                bars_i = stress_simulator_ohlc(raw_bars, i, stress_seed=neuro_stress_seed)
                m = ppo_trainer.evaluate_policy_zip_rollouts(
                    policy_path,
                    bars_i,
                    dna_hash=anchor_dna.hash,
                    shadow_max_steps=shadow_max_steps,
                    backtest_max_steps=backtest_max_steps,
                )
                if m.get("ok"):
                    m["_reality_id"] = i
                    evals.append(m)
            if not evals:
                return {"ok": False, "backtest_fitness": float("-inf"), "shadow_equity_delta": 0.0}
            return min(
                evals,
                key=lambda x: float(x.get("backtest_fitness", float("-inf")) or float("-inf")),
            )

        if use_ohlc_stress_rollouts:
            base_eval = _ppo_worst_across_ohlc_bars(baseline_snapshot, list(simulator_data))
        else:
            base_eval = ppo_trainer.evaluate_policy_zip_rollouts(
                baseline_snapshot,
                simulator_data,
                dna_hash=anchor_dna.hash,
                shadow_max_steps=shadow_max_steps,
                backtest_max_steps=backtest_max_steps,
            )
        if not base_eval.get("ok"):
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "baseline_rollout_failed",
                **_neuro_meta,
            }

        if not use_ohlc_stress_rollouts:
            base_eval = aggregate_ppo_eval_worst_reality(
                base_eval,
                eff_neuro_stress,
                stress_seed=neuro_stress_seed,
            )
        rollout_baseline = float(base_eval.get("backtest_fitness", float("-inf")))

        def _evaluate_candidate(weight_path: Path, _meta: dict[str, Any]) -> dict[str, Any]:
            if use_ohlc_stress_rollouts:
                metrics = _ppo_worst_across_ohlc_bars(weight_path, list(simulator_data))
            else:
                metrics = ppo_trainer.evaluate_policy_zip_rollouts(
                    weight_path,
                    simulator_data,
                    dna_hash=anchor_dna.hash,
                    shadow_max_steps=shadow_max_steps,
                    backtest_max_steps=backtest_max_steps,
                )
            if not metrics.get("ok"):
                return {"fitness": float("-inf"), "confidence": 0.0, "shadow_passed": False, "backtest_passed": False}

            if not use_ohlc_stress_rollouts:
                metrics = aggregate_ppo_eval_worst_reality(
                    metrics,
                    eff_neuro_stress,
                    stress_seed=neuro_stress_seed,
                )
            shadow_pnl = float(metrics.get("shadow_equity_delta", 0.0) or 0.0)
            candidate_fitness = float(metrics.get("backtest_fitness", float("-inf")))

            shadow_passed = self._guard.shadow_validation_passed(
                shadow_total_pnl=shadow_pnl,
                veto_blocked=False,
                risk_flags=[],
            )
            backtest_passed = bool(candidate_fitness > rollout_baseline)
            confidence = float(0.90 if backtest_passed else 0.80)

            return {
                "fitness": candidate_fitness,
                "confidence": confidence,
                "shadow_passed": shadow_passed,
                "backtest_passed": backtest_passed,
            }

        try:
            population_result = evaluate_weight_population(
                base_model,
                evaluator=_evaluate_candidate,
                population_size=population_size,
                mutation_std=mutation_std,
                mutation_rate=mutation_rate,
                crossover_ratio=crossover_ratio,
                output_dir=self._neuro_weights_path,
                max_workers=1,
                seed=_seed_from_hash(f"neuro:{anchor_dna.hash}:{generation_offset}"),
            )
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/orchestrator_core.py:971")
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "population_eval_failed",
                **_neuro_meta,
            }

        winner = population_result.get("winner") if isinstance(population_result, dict) else None
        if not isinstance(winner, dict):
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "reason": "no_passing_weight_candidate",
                **_neuro_meta,
            }

        winner_fitness = float(winner.get("fitness", float("-inf")) or float("-inf"))
        winner_confidence = float(winner.get("confidence", 0.0) or 0.0)
        accepted = self._guard.allows_neuroevolution_winner(
            candidate_confidence=winner_confidence,
            candidate_fitness=winner_fitness,
            current_fitness=rollout_baseline,
        )
        if not accepted:
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "winner_fitness": winner_fitness,
                "winner_confidence": winner_confidence,
                "reason": "guard_rejected_winner",
                **_neuro_meta,
            }

        winner_path = str(winner.get("path", "") or "")
        loaded_winner = ppo_trainer.load_weights(winner_path) if winner_path else None
        if loaded_winner is None:
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "reason": "winner_load_failed",
                **_neuro_meta,
            }

        return {
            "tested": len(list(population_result.get("evaluations", []) or [])),
            "winners": 1,
            "winner_accepted": True,
            "winner_fitness": winner_fitness,
            "winner_confidence": winner_confidence,
            "winner_path": winner_path,
            "evaluations": list(population_result.get("evaluations", []) or []),
            **_neuro_meta,
        }

