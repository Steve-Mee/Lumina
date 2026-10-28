"""Named daytrading hypothesis seeds — research challengers, not live strategies."""
from __future__ import annotations

import json
from typing import Any

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA

CATALOG_SEEDS: tuple[dict[str, Any], ...] = (
    {
        "candidate_name": "trend_follow_breakout",
        "strategy_family": "trend",
        "regime_focus": "trending",
        "prompt_tweak": "Trade with the session trend; enter on breakout+retest; skip chop.",
        "hyperparam_suggestion": {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0},
    },
    {
        "candidate_name": "vwap_deviation_fade",
        "strategy_family": "vwap",
        "regime_focus": "ranging",
        "prompt_tweak": "Fade extended VWAP deviation in range; exit at VWAP mean.",
        "hyperparam_suggestion": {"max_risk_percent": 0.75, "drawdown_kill_percent": 6.0},
    },
    {
        "candidate_name": "opening_range_breakout",
        "strategy_family": "orb",
        "regime_focus": "volatile",
        "prompt_tweak": "Opening-range breakout with failed-break fade filter.",
        "hyperparam_suggestion": {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0},
    },
    {
        "candidate_name": "range_mean_reversion",
        "strategy_family": "mean_reversion",
        "regime_focus": "ranging",
        "prompt_tweak": "Mean-revert inside range; no fade when ADX trend is strong.",
        "hyperparam_suggestion": {"max_risk_percent": 0.75, "drawdown_kill_percent": 6.0},
    },
    {
        "candidate_name": "session_vwap_trend",
        "strategy_family": "session",
        "regime_focus": "trending",
        "prompt_tweak": "Hold session VWAP trend continuation; flatten into close.",
        "hyperparam_suggestion": {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0},
    },
)


def catalog_seed_dna(*, generation: int, index: int) -> PolicyDNA:
    seed = CATALOG_SEEDS[index % len(CATALOG_SEEDS)]
    content = json.dumps({**seed, "source": "strategy_catalog"}, sort_keys=True, ensure_ascii=True)
    return PolicyDNA.create(
        prompt_id=f"catalog:{seed['candidate_name']}",
        version="catalog_seed",
        content=content,
        fitness_score=0.0,
        generation=int(generation),
        lineage_hash="CATALOG",
    )


def inject_catalog_challengers(
    registry: DNARegistry,
    candidates: list[PolicyDNA],
    *,
    generation_offset: int,
    max_inject: int = 2,
) -> list[PolicyDNA]:
    """Append up to max_inject catalog seeds not already in the candidate pool."""
    existing = {str(getattr(c, "prompt_id", "") or "") for c in candidates}
    out = list(candidates)
    injected = 0
    start = int(generation_offset) % len(CATALOG_SEEDS)
    for i in range(len(CATALOG_SEEDS)):
        if injected >= max_inject:
            break
        dna = catalog_seed_dna(generation=generation_offset, index=start + i)
        if dna.prompt_id in existing:
            continue
        registered = registry.register_dna(dna)
        out.append(registered)
        existing.add(dna.prompt_id)
        injected += 1
    return out
