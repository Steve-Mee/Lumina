"""
Risk Shadow Bridge — First Integration Point for Phase 2 Deliverable 5.

This thin, official adapter makes the risk-specific shadow aperture (the
isolated RiskOrchestrator + ShadowRiskEvaluator capability) easily callable
from the evolution layer when a proposed DNA change or experiment touches
risk logic, policy, limits, gates, or related parameters.

It exists so that "every evolution experiment that touches risk logic must
run in a shadow aperture mode" (original 2026-05-31 wording) can become
reality instead of remaining excellent but unused infrastructure.

All calls go through the official public API on RiskOrchestrator:
    orchestrator.run_shadow_risk_experiment(...)  / execute_...

This module deliberately stays thin. It does not duplicate risk logic,
does not implement promotion policy, and does not touch live capital paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.shadow import ShadowExperimentResult


def run_risk_shadow_experiment_for_proposal(
    *,
    proposal: dict[str, Any],
    engine: Any,
    market_context: dict[str, Any] | None = None,
    recent_fills: list[dict[str, Any]] | None = None,
    storage_path: str | Path | None = None,
    reference_experiment_id: str | None = None,
    auto_record_promotion: bool = False,
) -> ShadowExperimentResult:
    """
    Official entry point for evolution code to validate a risk-affecting
    change safely in shadow mode before any promotion consideration.

    The `proposal` dict should contain at minimum the fields needed to
    construct a risk decision experiment:
        - experiment_id (str)
        - dna_hash (str)
        - signal (str)
        - confluence_score (float)
        - proposed_risk (float)

    Optional keys that are passed through:
        - recent_fills
        - storage_path (overrides the parameter if present)
        - reference_experiment_id

    This function:
    - Creates a fresh RiskOrchestrator (via the engine).
    - Delegates exclusively to the official `run_shadow_risk_experiment`.
    - Returns the full rich result (including recommendation and
      human_approval_request when the recommendation requires human review).

    The result can be used directly to emit an EvolutionPromotionDecision
    with the appropriate stage ("shadow", "promotion_gate", "human_approval",
    or "final").

    When `auto_record_promotion=True` and a `storage_path` is provided,
    this function will automatically call `record_risk_shadow_promotion_decision`
    for you. This gives evolution callers a convenient one-shot path for
    the common case.
    """
    # Normalize inputs from the proposal dict (evolution layers often pass flat dicts)
    experiment_id = str(proposal.get("experiment_id") or proposal.get("id") or "risk-exp")
    dna_hash = str(proposal.get("dna_hash") or proposal.get("hash") or "unknown-dna")
    signal = str(proposal.get("signal", "BUY"))
    confluence_score = float(proposal.get("confluence_score", proposal.get("confluence", 0.5)))
    proposed_risk = float(proposal.get("proposed_risk", proposal.get("risk", 100.0)))

    # Allow proposal to carry recent_fills or storage_path for convenience
    effective_recent_fills = recent_fills or proposal.get("recent_fills")
    effective_storage = storage_path or proposal.get("storage_path")
    effective_reference = reference_experiment_id or proposal.get("reference_experiment_id")

    orchestrator = RiskOrchestrator(engine=engine)
    orchestrator.initialize()

    result = orchestrator.run_shadow_risk_experiment(
        experiment_id=experiment_id,
        dna_hash=dna_hash,
        signal=signal,
        confluence_score=confluence_score,
        proposed_risk=proposed_risk,
        recent_fills=effective_recent_fills,
        storage_path=effective_storage,
        reference_experiment_id=effective_reference,
    )

    if auto_record_promotion and effective_storage is not None:
        # One-shot ergonomic path: run + commit promotion decision in one call
        try:
            record_risk_shadow_promotion_decision(result, registry_path=effective_storage)
        except Exception:
            # Recording failure should never break the shadow run itself
            pass

    return result


def get_risk_shadow_human_review_package(
    experiment_id: str,
    engine: Any,
    storage_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """
    Convenience helper for the evolution layer / human review UI.

    After a shadow run has recommended human_approval, this returns the
    rich review package (decision summary + comparison + history) using
    the same storage the run used.
    """
    from lumina_core.risk.shadow_review import get_full_review_package

    return get_full_review_package(experiment_id, storage_path)


def record_risk_shadow_promotion_decision(
    shadow_result: ShadowExperimentResult,
    registry_path: str | Path | None = None,
) -> "EvolutionPromotionDecision":
    """
    Promotion gate automation helper for risk shadows (Phase 2 Deliverable 5).

    Takes the rich result from a risk shadow experiment and ensures the
    `EvolutionPromotionDecision` is durably recorded in the registry.

    - If the recommendation was "human_approval", the human review request
      is also recorded so it becomes visible to:
        * the `shadow_review` CLI (list / show / decide)
        * `get_risk_shadow_human_review_package(...)`

    - The full result is recorded for audit/history.

    This is the missing automation piece that lets evolution code run a
    risk experiment in shadow and then "commit" the outcome into the
    promotion flow with one extra call.

    Usage pattern (the intended flow for risk-affecting DNA changes):

        result = run_risk_shadow_experiment_for_proposal(...)
        decision = record_risk_shadow_promotion_decision(result, registry_path=...)

        if result.recommendation.get("suggested_stage") == "human_approval":
            # Human reviewer uses the existing CLI or dashboard
            package = get_risk_shadow_human_review_package(...)
    """
    from lumina_core.risk.shadow import ShadowRunRegistry
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision as _EvolutionPromotionDecision

    reg = ShadowRunRegistry(storage_path=registry_path) if registry_path else None

    decision = shadow_result.promotion_decision

    if reg is not None:
        try:
            reg.record_promotion_decision(shadow_result.experiment_id, decision)
        except Exception:
            pass

        # Ensure human approval request is recorded for the CLI and review tooling
        if shadow_result.human_approval_request:
            try:
                reg.record(
                    f"{shadow_result.experiment_id}:human_approval_request",
                    shadow_result.human_approval_request,
                )
            except Exception:
                pass

        # Record the full rich result for history / audit
        try:
            reg.record(shadow_result.experiment_id, shadow_result)
        except Exception:
            pass

    return decision


def validate_risk_proposal_in_shadow(
    *,
    proposal: dict[str, Any],
    engine: Any,
    storage_path: str | Path | None = None,
    auto_record_promotion: bool = True,
) -> ShadowExperimentResult | None:
    """
    Recommended high-level entry point for evolution code.

    Safely validates a proposal that touches risk logic, policy, limits,
    gates, or sizing through the isolated shadow aperture.

    By default, automatically records the promotion decision and any
    required human review request.

    This is the clean, reusable helper that makes it easy for any part
    of the evolution system to obey the "must run in shadow" rule for
    risk-affecting changes.

    Returns the full ShadowExperimentResult on success, or None if the
    run could not be completed (best-effort, never breaks the caller).
    """
    try:
        return run_risk_shadow_experiment_for_proposal(
            proposal=proposal,
            engine=engine,
            storage_path=storage_path,
            auto_record_promotion=auto_record_promotion,
        )
    except Exception:
        # Best-effort: risk shadow validation must never break evolution flows.
        return None


# =============================================================================
# Structural Enforcement Support for Phase 2 Deliverable 5 (first central hook)
# =============================================================================

# Simple process-lifetime de-duplication for the structural hook.
# Keeps memory bounded and prevents spamming duplicate shadow experiments
# for the same DNA content within a single run. Best-effort and fully reversible.
from collections import OrderedDict
import hashlib
import json as _json_for_hash

_SEEN_RISK_CONTENT_HASHES: OrderedDict[str, None] = OrderedDict()
_MAX_SEEN_RISK_HASHES = 2000


def _stable_content_hash(content: Any) -> str:
    """Stable short hash for de-duplication purposes."""
    if isinstance(content, (dict, list)):
        try:
            canonical = _json_for_hash.dumps(content, sort_keys=True, default=str)
        except Exception:
            canonical = str(content)
    else:
        canonical = str(content)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def detect_risk_proposal_from_content(content: Any) -> dict[str, Any] | None:
    """
    Reusable, central heuristic to decide whether a piece of DNA content
    (or a proposal dict) touches risk logic, policy, limits, or sizing.

    Returns a ready-to-pass proposal dict for validate_risk_proposal_in_shadow
    when risk-affecting signals are present. Returns None otherwise.

    This is the single source of truth for "does this DNA change affect risk?"
    used by the first structural hook in DNARegistry (and future paths).

    Detection combines:
    - Explicit risk hyperparams (max_risk_percent, drawdown_kill, proposed_risk, kelly, etc.)
    - Classic high-risk signals (high mutation_rate, martingale, etc.)
    """
    if content is None:
        return None

    # Normalize stringified JSON (very common for stored DNA content)
    if isinstance(content, str):
        try:
            import json
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                content = parsed
            else:
                content = {}
        except Exception:
            content = {}

    if not isinstance(content, dict):
        content = {}

    hp = content.get("hyperparam_suggestion") or {}
    if not isinstance(hp, dict):
        hp = {}

    risk_hyperparam_keys = {
        "max_risk_percent", "drawdown_kill_percent", "proposed_risk",
        "kelly", "position_size", "risk_limit", "sizing"
    }

    has_risk_hyperparam = any(
        k in hp or k in content for k in risk_hyperparam_keys
    )

    # Classic dangerous signals (reused/enhanced from prior D5 detection logic)
    mutation_rate = float(content.get("mutation_rate", 0) or 0)
    content_str = str(content).lower()

    high_risk_signal = (
        has_risk_hyperparam
        or mutation_rate > 0.35
        or "martingale" in content_str
        or ("aggressive" in content_str and "risk" in content_str)
        or any(k in content for k in ("risk", "sizing", "position", "exposure"))
    )

    if not high_risk_signal:
        return None

    # Build a useful proposal (best-effort values, similar to all previous wirings)
    proposed_risk = float(
        hp.get("max_risk_percent",
               hp.get("proposed_risk",
                      content.get("proposed_risk", 1.0)))
    )

    return {
        "experiment_id": "risk-dna-structural",
        "dna_hash": "structural-hook",
        "signal": "PROPOSAL",
        "confluence_score": 0.6,
        "proposed_risk": proposed_risk,
        "source": "dnaregistry_structural_hook",
        "mutation_rate": mutation_rate,
    }


def ensure_risk_shadow_for_dna_content(
    content: Any,
    *,
    engine: Any = None,
    storage_path: str | Path | None = None,
) -> None:
    """
    Best-effort structural helper.

    If the given DNA content looks risk-affecting, automatically run it
    through the isolated shadow aperture using the official bridge.

    This is the implementation of the first central structural enforcement
    step for Phase 2 Deliverable 5.
    """
    proposal = detect_risk_proposal_from_content(content)
    if not proposal:
        return

    # De-dupe: skip if we've already processed this exact content in this process
    chash = _stable_content_hash(content)
    if chash in _SEEN_RISK_CONTENT_HASHES:
        return
    _SEEN_RISK_CONTENT_HASHES[chash] = None
    if len(_SEEN_RISK_CONTENT_HASHES) > _MAX_SEEN_RISK_HASHES:
        _SEEN_RISK_CONTENT_HASHES.popitem(last=False)  # evict oldest

    try:
        validate_risk_proposal_in_shadow(
            proposal=proposal,
            engine=engine,
            storage_path=storage_path,
            auto_record_promotion=True,
        )
    except Exception:
        # Never allow the structural protection layer to break DNA creation.
        pass
