from __future__ import annotations

import hashlib
import os
import random
from datetime import datetime, timezone
from typing import Any, Final, Protocol

from lumina_core.config_loader import ConfigLoader

from .dna_registry import PolicyDNA
from .genetic_operators import calculate_fitness
from .meta_swarm import parallel_realities_from_config

CAPITAL_GUARD_DD: Final[float] = 25_000.0


class FitnessEvaluator(Protocol):
    def score(self, dna: PolicyDNA, base_metrics: dict[str, Any], generation: int) -> float:
        ...


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def seed_from_hash(h: str) -> int:
    return int(hashlib.sha256(h.encode()).hexdigest()[:8], 16)


def dream_engine_commit_hints_enabled() -> bool:
    evo = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(evo, dict):
        return True
    de = evo.get("dream_engine", {})
    if not isinstance(de, dict):
        return True
    return bool(de.get("commit_hints_to_bible", True))


def resolve_parallel_realities_count() -> int:
    return parallel_realities_from_config()


def resolve_dashboard_url() -> str:
    value = str(os.getenv("LUMINA_DASHBOARD_URL", "")).strip()
    if value:
        return value
    monitoring_cfg = ConfigLoader.section("monitoring", default={})
    if isinstance(monitoring_cfg, dict):
        value = str(monitoring_cfg.get("dashboard_url", "")).strip()
        if value:
            return value
    return ""


def score_candidate(dna: PolicyDNA, base_metrics: dict[str, Any], generation: int) -> float:
    rng = random.Random(seed_from_hash(dna.hash + str(generation)))
    base_pnl = float(base_metrics.get("net_pnl", 0.0) or 0.0)
    base_dd = abs(float(base_metrics.get("max_drawdown", 0.0) or 0.0))
    base_sharpe = float(base_metrics.get("sharpe", 0.0) or 0.0)
    pnl = base_pnl * (1.0 + rng.uniform(-0.15, 0.15))
    dd = base_dd * (1.0 + rng.uniform(-0.10, 0.10))
    sharpe = base_sharpe * (1.0 + rng.uniform(-0.15, 0.15))
    return calculate_fitness(pnl, dd, sharpe, capital_preservation_threshold=CAPITAL_GUARD_DD)
