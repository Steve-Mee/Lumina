from __future__ import annotations
import logging

import hashlib
import json
import math
from typing import Any, Protocol

from ..evolution.dna_registry import DNARegistry, PolicyDNA
from ..evolution.genetic_operators import calculate_fitness, crossover, mutate_prompt
from .errors import ErrorSeverity, LuminaError


class _ProposalOwner(Protocol):
    engine: Any
    dna_registry: DNARegistry
    blackboard: Any | None
    sim_mode: bool
    aggressive_evolution: bool
    max_mutation_depth: str


class ProposalGeneratorProtocol(Protocol):
    def current_champion(self) -> dict[str, Any]: ...

    def build_challengers(self, champion: dict[str, Any], meta_review: dict[str, Any]) -> list[dict[str, Any]]: ...


class ProposalGenerator:
    def __init__(self, owner: _ProposalOwner) -> None:
        self._owner = owner

    def dna_registry(self) -> DNARegistry:
        return self._owner.dna_registry

    def current_champion(self) -> dict[str, Any]:
        cfg = self._owner.engine.config
        return {
            "name": "champion",
            "prompt_fingerprint": self.prompt_fingerprint(),
            "hyperparams": {
                "risk_profile": str(getattr(cfg, "risk_profile", "balanced")),
                "max_risk_percent": float(getattr(cfg, "max_risk_percent", 1.0)),
                "drawdown_kill_percent": float(getattr(cfg, "drawdown_kill_percent", 8.0)),
                "fast_path_threshold": float(
                    getattr(cfg, "rl_confidence_threshold", 0.78) if hasattr(cfg, "rl_confidence_threshold") else 0.78
                ),
            },
        }

    def build_challengers(self, champion: dict[str, Any], meta_review: dict[str, Any]) -> list[dict[str, Any]]:
        h = dict(champion.get("hyperparams", {}))
        base_threshold = float(h.get("fast_path_threshold", 0.78))
        base_risk = float(h.get("max_risk_percent", 1.0))
        base_dd = float(h.get("drawdown_kill_percent", 8.0))
        weakest_regime = self.weakest_regime(meta_review)

        challengers: list[dict[str, Any]] = [
            {
                "name": "challenger_a",
                "prompt_tweak": f"More conservative under regime drift; prioritize HOLD when confidence split detected in {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(min(0.9, base_threshold + 0.04), 3),
                    "max_risk_percent": round(max(0.3, base_risk * 0.9), 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.95), 3),
                },
            },
            {
                "name": "challenger_b",
                "prompt_tweak": f"Increase trend-following bias when sharpe positive and RL drift low, but only outside weak regime {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(max(0.6, base_threshold - 0.03), 3),
                    "max_risk_percent": round(min(2.0, base_risk * 1.05), 3),
                    "drawdown_kill_percent": round(min(15.0, base_dd * 1.02), 3),
                },
            },
            {
                "name": "challenger_c",
                "prompt_tweak": f"Hybrid mode: strict risk gate + adaptive execution latency guard optimized for {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(base_threshold, 3),
                    "max_risk_percent": round(base_risk, 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.98), 3),
                },
            },
        ]

        if self._owner.sim_mode or self._owner.aggressive_evolution or self._owner.max_mutation_depth == "radical":
            challengers.extend(
                [
                    {
                        "name": "challenger_radical_indicators",
                        "prompt_tweak": (
                            f"RADICAL MUTATION: add/remove indicators dynamically for {weakest_regime}; "
                            "permit structural feature set changes and aggressively reweight signal stack."
                        ),
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": {
                            "fast_path_threshold": round(max(0.5, base_threshold - 0.08), 3),
                            "max_risk_percent": round(min(3.0, base_risk * 1.25), 3),
                            "drawdown_kill_percent": round(min(25.0, base_dd * 1.25), 3),
                        },
                    },
                    {
                        "name": "challenger_radical_prompts",
                        "prompt_tweak": (
                            "RADICAL MUTATION: rewrite confluence rules and prompt scaffolding end-to-end; "
                            "allow hard prompt rewrites and non-linear decision-policy restructuring."
                        ),
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": {
                            "fast_path_threshold": round(max(0.45, base_threshold - 0.1), 3),
                            "max_risk_percent": round(min(3.5, base_risk * 1.35), 3),
                            "drawdown_kill_percent": round(min(30.0, base_dd * 1.4), 3),
                        },
                    },
                ]
            )
        return challengers

    def score_challenger(
        self,
        champion: dict[str, Any],
        challenger: dict[str, Any],
        report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> dict[str, Any]:
        del champion
        win_rate = float(meta_review.get("win_rate", 0.0))
        sharpe = float(meta_review.get("sharpe", 0.0))
        regime_drift = float(meta_review.get("regime_drift", 0.5))
        rl_drift = float(meta_review.get("rl_drift", 0.5))
        emotional_accuracy = float(meta_review.get("emotional_twin_accuracy", 0.5))
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        quality = (
            (win_rate * 30.0)
            + (max(-1.0, min(2.0, sharpe)) * 8.0)
            + ((1.0 - regime_drift) * 12.0)
            + ((1.0 - rl_drift) * 12.0)
            + (emotional_accuracy * 10.0)
            + (8.0 if net_pnl > 0 else -8.0)
        )
        suggestion = challenger.get("hyperparam_suggestion", {})
        risk_penalty = 0.0
        if float(suggestion.get("max_risk_percent", 1.0)) > float(
            getattr(self._owner.engine.config, "max_risk_percent", 1.0)
        ):
            risk_penalty += 2.5
        if float(suggestion.get("drawdown_kill_percent", 8.0)) > float(
            getattr(self._owner.engine.config, "drawdown_kill_percent", 8.0)
        ):
            risk_penalty += 2.0
        score = max(0.0, quality - risk_penalty)
        confidence = max(0.0, min(99.0, 50.0 + score))
        out = dict(challenger)
        out["score"] = round(score, 4)
        out["confidence"] = round(confidence, 2)
        out["risk_penalty"] = round(risk_penalty, 2)
        return out

    def top_ranked_dna(self, *, active_dna: PolicyDNA | None) -> list[PolicyDNA]:
        registry = self.dna_registry()
        ranked = registry.get_ranked_dna(limit=3, versions=("active", "candidate"))
        if ranked:
            return ranked
        return [active_dna] if active_dna is not None else []

    def build_genetic_candidates(
        self,
        *,
        champion: dict[str, Any],
        top_dna: list[PolicyDNA],
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
        fitness_score: float,
    ) -> tuple[list[dict[str, Any]], dict[str, PolicyDNA]]:
        if not top_dna:
            return [], {}
        registry = self.dna_registry()
        weakest_regime = self.weakest_regime(meta_review)
        lineage_hash = self.dna_lineage_hash()
        candidates: list[dict[str, Any]] = []
        candidate_map: dict[str, PolicyDNA] = {}
        mutation_rates = [0.12, 0.18, 0.24, 0.3, 0.36]

        for index, parent in enumerate(top_dna[:3]):
            mutation_rate = mutation_rates[index % len(mutation_rates)]
            mutated_prompt = mutate_prompt(self.prompt_source_from_dna(parent), mutation_rate)
            draft = registry.mutate(
                parent=parent,
                mutation_rate=mutation_rate,
                content={
                    "candidate_name": f"genetic_mutant_{index + 1}",
                    "prompt_tweak": mutated_prompt,
                    "regime_focus": weakest_regime,
                    "hyperparam_suggestion": self.mutated_hyperparams(
                        parent=parent, scale=mutation_rate, champion=champion
                    ),
                },
                fitness_score=fitness_score,
                version="candidate",
                lineage_hash=lineage_hash,
            )
            draft = registry.register_dna(draft)
            candidate = self.candidate_from_dna(draft)
            candidates.append(candidate)
            candidate_map[draft.hash] = draft

        crossover_pairs = [(0, 1), (0, 2), (1, 2)]
        for left_index, right_index in crossover_pairs:
            if left_index >= len(top_dna) or right_index >= len(top_dna):
                continue
            left_parent = top_dna[left_index]
            right_parent = top_dna[right_index]
            crossed_prompt = crossover(left_parent, right_parent)
            draft = registry.mutate(
                parent=left_parent,
                crossover=right_parent,
                mutation_rate=0.22,
                content={
                    "candidate_name": f"genetic_crossover_{left_index + 1}_{right_index + 1}",
                    "prompt_tweak": crossed_prompt,
                    "regime_focus": weakest_regime,
                    "hyperparam_suggestion": self.blended_hyperparams(
                        left_parent=left_parent, right_parent=right_parent, champion=champion
                    ),
                },
                fitness_score=fitness_score,
                version="candidate",
                lineage_hash=lineage_hash,
            )
            draft = registry.register_dna(draft)
            candidate = self.candidate_from_dna(draft)
            candidates.append(candidate)
            candidate_map[draft.hash] = draft

        if len(candidates) < 5 and top_dna:
            filler_parent = top_dna[0]
            while len(candidates) < 5:
                mutation_rate = mutation_rates[len(candidates) % len(mutation_rates)]
                mutated_prompt = mutate_prompt(self.prompt_source_from_dna(filler_parent), mutation_rate)
                draft = registry.mutate(
                    parent=filler_parent,
                    mutation_rate=mutation_rate,
                    content={
                        "candidate_name": f"genetic_filler_{len(candidates) + 1}",
                        "prompt_tweak": mutated_prompt,
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": self.mutated_hyperparams(
                            parent=filler_parent, scale=mutation_rate, champion=champion
                        ),
                    },
                    fitness_score=fitness_score,
                    version="candidate",
                    lineage_hash=lineage_hash,
                )
                draft = registry.register_dna(draft)
                candidate = self.candidate_from_dna(draft)
                candidates.append(candidate)
                candidate_map[draft.hash] = draft

        del nightly_report
        return candidates[:10], candidate_map

    def promote_winning_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        winner_dna: PolicyDNA | None,
        should_promote: bool,
    ) -> PolicyDNA | None:
        if not should_promote or winner_dna is None:
            return active_dna
        registry = self.dna_registry()
        promoted = PolicyDNA.create(
            prompt_id=winner_dna.prompt_id,
            version="active",
            content=winner_dna.content,
            fitness_score=winner_dna.fitness_score,
            generation=max(int(winner_dna.generation), int(active_dna.generation) + 1 if active_dna else 1),
            parent_ids=[winner_dna.hash],
            mutation_rate=0.0,
            lineage_hash=self.dna_lineage_hash(),
        )
        return registry.register_dna(promoted)

    def register_active_dna(
        self,
        *,
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
        dna_fitness: float,
    ) -> PolicyDNA | None:
        registry = self.dna_registry()
        if registry.get_latest_dna("active") is None:
            registry.load_from_blackboard(
                self._owner.blackboard, prompt_id="self_evolution_blackboard", version="bootstrap"
            )
        payload = {
            "prompt_fingerprint": self.prompt_fingerprint(),
            "agent_styles": dict(getattr(self._owner.engine.config, "agent_styles", {}) or {}),
            "hyperparams": dict(self.current_champion().get("hyperparams", {})),
            "nightly_report": {
                "trades": int(nightly_report.get("trades", 0) or 0),
                "wins": int(nightly_report.get("wins", 0) or 0),
                "net_pnl": float(nightly_report.get("net_pnl", 0.0) or 0.0),
                "sharpe": float(nightly_report.get("sharpe", 0.0) or 0.0),
            },
            "meta_review": dict(meta_review),
        }
        previous = registry.get_latest_dna("active")
        generation = 0 if previous is None else int(previous.generation)
        parent_ids = [] if previous is None else [previous.hash]
        dna = PolicyDNA.create(
            prompt_id="self_evolution_policy",
            version="active",
            content=payload,
            fitness_score=dna_fitness,
            generation=generation,
            parent_ids=parent_ids,
            mutation_rate=0.0,
            lineage_hash=self.dna_lineage_hash(),
        )
        return registry.register_dna(dna)

    def register_candidate_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        best: dict[str, Any] | None,
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
        dna_fitness: float,
    ) -> PolicyDNA | None:
        if active_dna is None or best is None:
            return None
        registry = self.dna_registry()
        mutation_rate = 0.35 if self._owner.sim_mode else 0.1
        content = {
            "candidate_name": str(best.get("name", "candidate")),
            "prompt_tweak": str(best.get("prompt_tweak", "")),
            "regime_focus": str(best.get("regime_focus", "neutral")),
            "hyperparam_suggestion": dict(best.get("hyperparam_suggestion", {})),
            "score": float(best.get("score", 0.0) or 0.0),
            "confidence": float(best.get("confidence", 0.0) or 0.0),
            "nightly_report": {
                "trades": int(nightly_report.get("trades", 0) or 0),
                "wins": int(nightly_report.get("wins", 0) or 0),
                "net_pnl": float(nightly_report.get("net_pnl", 0.0) or 0.0),
            },
            "meta_review": dict(meta_review),
        }
        dna = registry.mutate(
            parent=active_dna,
            mutation_rate=mutation_rate,
            content=content,
            fitness_score=dna_fitness,
            version="candidate",
            lineage_hash=self.dna_lineage_hash(),
        )
        return registry.register_dna(dna)

    def dna_lineage_hash(self) -> str:
        if self._owner.blackboard is None or not hasattr(self._owner.blackboard, "latest"):
            return self.prompt_fingerprint()
        lineage_parts: list[str] = []
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", "execution.aggregate"):
            try:
                event = self._owner.blackboard.latest(topic)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/proposal_generator.py:370")
                event = None
            if event is None:
                continue
            lineage_parts.append(str(getattr(event, "event_hash", "GENESIS") or "GENESIS"))
        if not lineage_parts:
            return self.prompt_fingerprint()
        return hashlib.sha256("|".join(lineage_parts).encode("utf-8")).hexdigest()

    def prompt_fingerprint(self) -> str:
        agent_styles = dict(getattr(self._owner.engine.config, "agent_styles", {}) or {})
        payload = json.dumps(agent_styles, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def dna_summary(dna: PolicyDNA | None) -> dict[str, Any] | None:
        if dna is None:
            return None
        return {
            "prompt_id": dna.prompt_id,
            "version": dna.version,
            "hash": dna.hash,
            "generation": dna.generation,
            "fitness_score": dna.fitness_score,
            "lineage_hash": dna.lineage_hash,
        }

    @staticmethod
    def content_from_dna(dna: PolicyDNA) -> dict[str, Any]:
        try:
            payload = json.loads(dna.content)
        except json.JSONDecodeError as exc:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="DNA_CONTENT_NOT_JSON_OBJECT",
                message="DNA content must be valid JSON object payload.",
                context={"prompt_id": str(dna.prompt_id), "hash": str(dna.hash)},
            ) from exc
        if not isinstance(payload, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="DNA_CONTENT_INVALID",
                message="DNA content must be a JSON object payload.",
            )
        return payload

    @classmethod
    def prompt_source_from_dna(cls, dna: PolicyDNA) -> str:
        payload = cls.content_from_dna(dna)
        for key in ("prompt_tweak", "candidate_name", "prompt_fingerprint"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return dna.content

    @classmethod
    def normalized_hyperparams(cls, dna: PolicyDNA, champion: dict[str, Any]) -> dict[str, float]:
        payload = cls.content_from_dna(dna)
        source = payload.get("hyperparam_suggestion") or payload.get("hyperparams") or champion.get("hyperparams", {})
        return {
            "fast_path_threshold": float(
                source.get("fast_path_threshold", source.get("rl_confidence_threshold", 0.78)) or 0.78
            ),
            "max_risk_percent": float(source.get("max_risk_percent", 1.0) or 1.0),
            "drawdown_kill_percent": float(source.get("drawdown_kill_percent", 8.0) or 8.0),
        }

    @classmethod
    def mutated_hyperparams(cls, *, parent: PolicyDNA, scale: float, champion: dict[str, Any]) -> dict[str, float]:
        base = cls.normalized_hyperparams(parent, champion)
        return {
            "fast_path_threshold": round(max(0.45, min(0.95, base["fast_path_threshold"] + (scale / 4.0))), 3),
            "max_risk_percent": round(max(0.2, min(3.5, base["max_risk_percent"] * (1.0 - (scale / 3.0)))), 3),
            "drawdown_kill_percent": round(
                max(2.0, min(20.0, base["drawdown_kill_percent"] * (1.0 - (scale / 5.0)))), 3
            ),
        }

    @classmethod
    def blended_hyperparams(
        cls, *, left_parent: PolicyDNA, right_parent: PolicyDNA, champion: dict[str, Any]
    ) -> dict[str, float]:
        left = cls.normalized_hyperparams(left_parent, champion)
        right = cls.normalized_hyperparams(right_parent, champion)
        return {
            "fast_path_threshold": round((left["fast_path_threshold"] + right["fast_path_threshold"]) / 2.0, 3),
            "max_risk_percent": round((left["max_risk_percent"] + right["max_risk_percent"]) / 2.0, 3),
            "drawdown_kill_percent": round((left["drawdown_kill_percent"] + right["drawdown_kill_percent"]) / 2.0, 3),
        }

    @classmethod
    def candidate_from_dna(cls, dna: PolicyDNA) -> dict[str, Any]:
        payload = cls.content_from_dna(dna)
        for required_key in ("candidate_name", "prompt_tweak", "regime_focus", "hyperparam_suggestion"):
            if required_key not in payload:
                raise LuminaError(
                    severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                    code="DNA_CANDIDATE_PAYLOAD_INCOMPLETE",
                    message=f"Missing required DNA candidate field: {required_key}",
                )
        return {
            "name": str(payload["candidate_name"]),
            "prompt_tweak": str(payload["prompt_tweak"]),
            "regime_focus": str(payload["regime_focus"]),
            "hyperparam_suggestion": dict(payload["hyperparam_suggestion"]),
            "dna_hash": dna.hash,
            "dna_generation": dna.generation,
            "mutation_rate": dna.mutation_rate,
        }

    @staticmethod
    def weakest_regime(meta_review: dict[str, Any]) -> str:
        breakdown = meta_review.get("regime_breakdown", {})
        if not isinstance(breakdown, dict) or not breakdown:
            return "neutral"
        weakest = min(
            breakdown.items(),
            key=lambda item: (float(item[1].get("net_pnl", 0.0)), float(item[1].get("winrate", 0.0))),
        )
        return str(weakest[0]).lower()

    @staticmethod
    def genetic_fitness(nightly_report: dict[str, Any], drawdown_kill_percent: float) -> float:
        fitness = calculate_fitness(
            float(nightly_report.get("net_pnl", 0.0) or 0.0),
            float(nightly_report.get("max_drawdown", 0.0) or 0.0),
            float(nightly_report.get("sharpe", 0.0) or 0.0),
            capital_preservation_threshold=max(5000.0, float(drawdown_kill_percent or 8.0) * 3000.0),
        )
        if not math.isfinite(fitness):
            return -1_000_000_000.0
        return round(float(fitness), 6)
