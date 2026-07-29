"""Risk-shadow emit / DNA registry wiring for ProposalGenerator."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from ..evolution.dna_registry import PolicyDNA
from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
from lumina_core.engine.evolution_risk_proposal import ensure_candidate_has_shadow_ref


def emit_risk_shadow_for_proposals(
    items: list[dict[str, Any]],
    *,
    engine: Any,
    experiment_id_prefix: str,
    default_dna_hash: str = "meta-proposal",
) -> None:
    """Best-effort shadow validation + creation-firewall ref attach for risk hyperparams.

    Never raises into the caller — shadow validation must not break proposal generation.
    """
    try:
        from lumina_core.evolution.risk_shadow_bridge import validate_risk_proposal_in_shadow

        for item in items:
            hp = item.get("hyperparam_suggestion") or item.get("content", {}).get("hyperparam_suggestion") or {}
            if not any(k in hp for k in ("max_risk_percent", "drawdown_kill_percent", "fast_path_threshold")):
                continue
            local_exp_id = (
                f"{experiment_id_prefix}-{item.get('name', item.get('candidate_name', 'unknown'))}"
            )
            ensure_candidate_has_shadow_ref(item, local_exp_id)
            validate_risk_proposal_in_shadow(
                proposal={
                    "experiment_id": local_exp_id,
                    "dna_hash": item.get("hash", item.get("dna_hash", default_dna_hash)),
                    "signal": "PROPOSAL",
                    "confluence_score": 0.6,
                    "proposed_risk": float(hp.get("max_risk_percent", hp.get("drawdown_kill_percent", 1.0))),
                },
                engine=engine,
                storage_path=Path("state/risk_shadow_evolution.jsonl"),
                auto_record_promotion=True,
            )
    except Exception:
        pass


class ProposalEmitMixin:
    """DNA register/promote wiring and lineage helpers mixed into ProposalGenerator."""

    __slots__ = ()

    def top_ranked_dna(self, *, active_dna: PolicyDNA | None) -> list[PolicyDNA]:
        registry = self.dna_registry()
        ranked = registry.get_ranked_dna(limit=3, versions=("active", "candidate"))
        if ranked:
            return ranked
        return [active_dna] if active_dna is not None else []

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
                self._owner.blackboard,
                event_bus=getattr(self._owner.engine, "event_bus", None),
                prompt_id="self_evolution_blackboard",
                version="bootstrap",
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
        bb = self._owner.blackboard
        eb = getattr(self._owner.engine, "event_bus", None)
        if (bb is None or not hasattr(bb, "latest")) and (eb is None or not hasattr(eb, "latest")):
            return self.prompt_fingerprint()
        lineage_parts: list[str] = []
        exec_topic = TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", exec_topic):
            event = None
            try:
                if topic == exec_topic:
                    if eb is not None and hasattr(eb, "latest"):
                        event = eb.latest(exec_topic)
                elif bb is not None and hasattr(bb, "latest"):
                    event = bb.latest(topic)
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/engine/proposal_generator.py:370"
                )
                event = None
            if event is None:
                continue
            ev_hash = getattr(event, "event_hash", None)
            if not ev_hash and hasattr(event, "to_dict"):
                ev_hash = hashlib.sha256(
                    json.dumps(event.to_dict(), sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
            lineage_parts.append(str(ev_hash or "GENESIS"))
        if not lineage_parts:
            return self.prompt_fingerprint()
        return hashlib.sha256("|".join(lineage_parts).encode("utf-8")).hexdigest()


__all__ = ["ProposalEmitMixin", "emit_risk_shadow_for_proposals"]
