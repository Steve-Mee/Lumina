from __future__ import annotations

import json
import logging
import random
from typing import Any, Protocol

from lumina_core.safety.constitutional_guard import ConstitutionalGuard

from .dna_registry import DNARegistry, PolicyDNA
from .dream_engine import merge_dream_hyperparam_nudges
from .fitness_evaluator import score_candidate
from .genetic_operators import crossover, mutate_prompt


def coerce_dna_content_to_structured_json(content: Any) -> str:
    raw = content if isinstance(content, str) else json.dumps(content, sort_keys=True, ensure_ascii=True)
    stripped = str(raw).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and obj:
                return json.dumps(obj, sort_keys=True, ensure_ascii=True)
        except json.JSONDecodeError:
            pass
    snippet = stripped[:8000]
    return json.dumps(
        {
            "candidate_name": "mutation_candidate",
            "prompt_tweak": snippet,
            "regime_focus": "neutral",
            "hyperparam_suggestion": {
                "max_risk_percent": 1.0,
                "drawdown_kill_percent": 8.0,
            },
        },
        sort_keys=True,
        ensure_ascii=True,
    )


def apply_dream_learnings_to_dna_content(
    content: Any,
    dream_report: dict[str, Any] | None,
    *,
    evolution_mode: str = "sim",
) -> Any:
    if not dream_report or not dream_report.get("enabled", True):
        return content
    hints = [str(x) for x in (dream_report.get("rule_hints") or []) if str(x).strip()]
    br = float(dream_report.get("breach_rate", 0.0) or 0.0)
    wdd = float(dream_report.get("worst_dd_ratio", 0.0) or 0.0)
    blurb = (
        f" [dream_learn: stress_breach={br:.3f} worst_dd~={wdd:.3f}{'; focus: ' + ', '.join(hints) if hints else ''}]"
    )
    c = str(content or "").strip()
    if c.startswith("{") and c.endswith("}"):
        try:
            d = json.loads(c)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/mutation_pipeline.py:61")
            return c + blurb
        if isinstance(d, dict):
            d2 = dict(d)
            d2["dream_learnings"] = {
                "breach_rate": br,
                "worst_dd_ratio": wdd,
                "rule_hints": hints,
            }
            raw_hs = d2.get("hyperparam_suggestion")
            if isinstance(raw_hs, dict):
                base_hs = {
                    "max_risk_percent": float(raw_hs.get("max_risk_percent", 1.0) or 1.0),
                    "drawdown_kill_percent": float(raw_hs.get("drawdown_kill_percent", 8.0) or 8.0),
                }
            else:
                base_hs = {
                    "max_risk_percent": 1.0,
                    "drawdown_kill_percent": 8.0,
                }
            nudged = merge_dream_hyperparam_nudges(base_hs, dream_report, evolution_mode=evolution_mode)
            d2["hyperparam_suggestion"] = {
                "max_risk_percent": float(nudged["max_risk_percent"]),
                "drawdown_kill_percent": float(nudged["drawdown_kill_percent"]),
            }
            if nudged.get("_nudged"):
                d2["dream_risk_nudge"] = {
                    "applied": True,
                    "evolution_mode": str(evolution_mode),
                    "source_hints": list(hints),
                }
            base_pt = str(d2.get("prompt_tweak", "") or "")
            d2["prompt_tweak"] = (base_pt + blurb)[:8000]
            return json.dumps(d2, sort_keys=True, ensure_ascii=True)
    return c + blurb


class MutationPipelineProtocol(Protocol):
    def generate_candidates(
        self,
        *,
        top_dna: list[PolicyDNA],
        active_dna: PolicyDNA | None,
        generation_offset: int,
        dream_report: dict[str, Any] | None = None,
        evolution_mode: str = "sim",
    ) -> list[PolicyDNA]: ...

    def bootstrap_active_dna(self, *, base_metrics: dict[str, Any]) -> PolicyDNA: ...


class MutationPipeline:
    def __init__(
        self,
        *,
        registry: DNARegistry,
        constitutional_guard: ConstitutionalGuard,
        logger: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._constitutional_guard = constitutional_guard
        self._logger = logger or logging.getLogger(__name__)

    def bootstrap_active_dna(self, *, base_metrics: dict[str, Any]) -> PolicyDNA:
        fitness = score_candidate(
            PolicyDNA.create(
                prompt_id="bootstrap_seed",
                version="candidate",
                content={
                    "candidate_name": "bootstrap_seed",
                    "prompt_tweak": "Bootstrap evolution seed policy",
                    "regime_focus": "neutral",
                    "hyperparam_suggestion": {
                        "fast_path_threshold": 0.78,
                        "max_risk_percent": 1.0,
                        "drawdown_kill_percent": 8.0,
                    },
                },
                fitness_score=0.0,
                generation=0,
                lineage_hash="GENESIS",
            ),
            base_metrics=base_metrics,
            generation=0,
        )
        seed = PolicyDNA.create(
            prompt_id="bootstrap_seed",
            version="active",
            content={
                "candidate_name": "bootstrap_seed",
                "prompt_tweak": "Bootstrap evolution seed policy",
                "regime_focus": "neutral",
                "hyperparam_suggestion": {
                    "fast_path_threshold": 0.78,
                    "max_risk_percent": 1.0,
                    "drawdown_kill_percent": 8.0,
                },
            },
            fitness_score=fitness,
            generation=0,
            lineage_hash="GENESIS",
        )
        return self._registry.register_dna(seed)

    def generate_candidates(
        self,
        *,
        top_dna: list[PolicyDNA],
        active_dna: PolicyDNA | None,
        generation_offset: int,
        dream_report: dict[str, Any] | None = None,
        evolution_mode: str = "sim",
    ) -> list[PolicyDNA]:
        if not top_dna and active_dna is None:
            return []

        seed_pool = list(top_dna) or []
        if active_dna is not None and not any(d.hash == active_dna.hash for d in seed_pool):
            seed_pool.insert(0, active_dna)

        stress = float((dream_report or {}).get("breach_rate", 0.0) or 0.0)
        target_count = random.randint(6, 8) if stress > 0.18 else random.randint(5, 8)
        candidates: list[PolicyDNA] = []
        base = seed_pool[0]
        for i in range(target_count):
            rate = round(0.1 + (i * 0.1), 2)
            if i < 4 or len(seed_pool) < 2:
                new_content = mutate_prompt(base.content, rate)
                new_content = apply_dream_learnings_to_dna_content(
                    new_content, dream_report, evolution_mode=evolution_mode
                )
                new_content = coerce_dna_content_to_structured_json(new_content)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=base.fitness_score,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                )
            else:
                other = seed_pool[i % len(seed_pool)]
                new_content = crossover(base, other)
                new_content = apply_dream_learnings_to_dna_content(
                    new_content, dream_report, evolution_mode=evolution_mode
                )
                new_content = coerce_dna_content_to_structured_json(new_content)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=(base.fitness_score + other.fitness_score) / 2.0,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                    crossover=other,
                )

            pre_check = self._constitutional_guard.check_pre_mutation(candidate.content, mode=evolution_mode)
            if not pre_check.passed:
                self._logger.warning(
                    "Pre-mutation check blocked candidate %s: %s",
                    candidate.hash[:12],
                    pre_check.violation_names,
                )
                continue
            self._registry.register_dna(candidate)
            candidates.append(candidate)
        return candidates
