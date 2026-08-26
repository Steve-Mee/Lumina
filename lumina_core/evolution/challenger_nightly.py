"""Nightly code-evolution → challenger store only (K8/K9)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.code_evolution.pipeline import run_code_evolution_dry_cycle
from lumina_core.code_evolution.runtime_role import is_real_like_capital
from lumina_core.evolution.challenger_venue.slot import try_occupy
from lumina_core.evolution.invalidation import (
    BEHAVIOR_TWEAK,
    classify_code_proposal,
)
from lumina_core.evolution.fitness_ssot import heuristic_fitness_allowed


CODE_MIN_DAYS = 5
CODE_MIN_TRADES = 50


def maybe_run_challenger_code_cycle(
    agent: Any,
    *,
    mode_key: str,
    mutation_allowed: bool,
    dry_run: bool,
    workspace: Path | str | None = None,
) -> dict[str, Any]:
    if is_real_like_capital(mode_key):
        return {"status": "blocked_real_like", "applied": False}
    if not mutation_allowed:
        return {"status": "mutation_not_allowed", "applied": False}

    evo_cfg = {}
    try:
        from lumina_core.config_loader import ConfigLoader

        evo_cfg = ConfigLoader.section("evolution", default={}) or {}
    except Exception:
        evo_cfg = {}
    ce = evo_cfg.get("code_evolution", {}) if isinstance(evo_cfg, dict) else {}
    if not isinstance(ce, dict):
        ce = {}
    enabled = bool(ce.get("enabled", False)) and bool(ce.get("nightly", False))
    if not enabled:
        return {"status": "disabled", "applied": False}

    journal_root = Path(workspace or ".") / "state" / "code_evolution"

    result = run_code_evolution_dry_cycle(
        enabled=True,
        max_proposals_per_cycle=int(ce.get("max_proposals_per_cycle", 1) or 1),
        mode="sim",
        twin=getattr(agent, "approval_twin", None) or getattr(agent, "_approval_twin", None),
        event_bus=getattr(agent, "event_bus", None),
        constitutional_guard=getattr(agent, "constitutional_guard", None),
        journal_root=journal_root,
        timeout_s=int(ce.get("sandbox_timeout_s", 30) or 30),
        require_twin=bool(ce.get("require_twin", True)),
        apply_policy={
            "apply_to_sandbox_store": bool(ce.get("apply_to_sandbox_store", False)) and not dry_run,
            "require_human_approve_for_apply": bool(ce.get("require_human_approve_for_apply", True)),
            "allow_twin_judgment_apply": bool(ce.get("allow_twin_judgment_apply", False)),
            "forbid_apply_in_real_capital": True,
        },
    )
    classes: list[str] = []
    for prop in result.get("proposals") or []:
        classes.append(classify_code_proposal(prop if not isinstance(prop, dict) else prop))

    candidate_id = "nightly"
    if result.get("proposals"):
        first = result["proposals"][0]
        candidate_id = str(first.get("proposal_id") if isinstance(first, dict) else getattr(first, "proposal_id", "nightly"))

    fitness = float("-inf") if not heuristic_fitness_allowed() else 0.0
    slot = try_occupy(Path(workspace or "."), candidate_id=candidate_id, fitness=fitness)
    inv = classes[0] if classes else "policy_incompatible"

    from lumina_core.evolution.challenger_venue.card import build_daily_card
    from lumina_core.evolution.challenger_venue.proof import venue_proof
    from lumina_core.evolution.invalidation import POLICY_INCOMPATIBLE
    from lumina_core.evolution.playground_reentry import request_playground_reentry

    ws = Path(workspace or ".")
    card = build_daily_card(ws)
    runtime = getattr(agent, "challenger_venue_runtime", None)
    if runtime is None:
        runtime = getattr(getattr(agent, "engine", None), "challenger_venue_runtime", None)
    gap_passed = False
    if runtime is not None and hasattr(runtime, "gap"):
        gap_passed = bool((runtime.gap() or {}).get("passed"))
    proof = venue_proof(
        ws,
        min_days=CODE_MIN_DAYS,
        min_trades=CODE_MIN_TRADES,
        gap_passed=gap_passed,
    )
    playground = {"ok": False}
    steve_notify: dict[str, Any] | None = None
    if inv == POLICY_INCOMPATIBLE:
        playground = request_playground_reentry(ws, invalidation=inv, steve_approved=False)
    if proof.get("notify_allowed"):
        from lumina_core.evolution.council import compose_dossier
        from lumina_core.evolution.council_notify import notify_council

        question = (
            "Playground re-entry for policy_incompatible (skip Birth)?"
            if inv == POLICY_INCOMPATIBLE
            else "NT SIM A/B for behavior_tweak challenger?"
        )
        steve_notify = notify_council(
            ws,
            "sim",
            compose_dossier(
                question=question,
                twin_values_ok=True,
                constitution_violations=0,
                risk_dd=0.0,
                swarm_fitness_delta=0.0,
                evolution_proof_passed=True,
            ),
        )
    return {
        "status": "ran",
        "applied": any(bool(d.get("applied")) for d in (result.get("decisions") or []) if isinstance(d, dict)),
        "invalidation": inv,
        "behavior_tweak": inv == BEHAVIOR_TWEAK,
        "min_days": CODE_MIN_DAYS,
        "min_trades": CODE_MIN_TRADES,
        "slot": slot,
        "cycle": result,
        "proof": proof,
        "card": card,
        "playground": playground,
        "steve_notify": steve_notify,
        "starts_birth": False,
    }
