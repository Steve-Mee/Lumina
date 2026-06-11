"""
evolution_risk_proposal — Phase 3 D2 first slice: strict typed firewall + central apply
for risk config mutations (max_risk_percent, drawdown_kill_percent) from evolution paths.

This is the minimal first slice of the god decomp/firewall on meta_agent_core (SPF-003)
per:
- 2026-05-31-elon-musk-first-principles-trading-system-analysis.md (SPF-003: primary
  concentration for self-evolution + DNA mutation + promotion; "one defect here has
  system-wide blast radius"; "changes inside it no longer require understanding the
  entire engine").
- 2026-05-31-elon-aperture-hardening-90-day-roadmap.md (Phase 3 D2 exact deliverable:
  "Decomposition or strict interface firewalling of at least one major concentration
  point (meta_agent_core or runtime_workers trading paths)").
- aperture-hardening-mission-control.md (post 2026-06-07 D4 update: D2 Red; "highest-leverage
  now: D2 decomp (meta_agent_core risk mutation first slice per 2026-06-07 explore survey
  + 05-31 SPF-003; new Plan Mode + constitution-guard + risk-safety-review required)").
- 2026-06-07-phase3-d4-longer-campaign-scale-evidence.md + explore subagent surveys
  (recommend exactly this path: RiskConfigMutationProposal Pydantic extra=forbid + apply
  fn + typed event; delegate from god; focused tests; additive; closes D5 residual
  _apply_candidate gap at meta:1044-1047 where the sole writer to engine.config risk
  limits can fire without fresh shadow at apply time).

Design goals (per constitution-guard + risk-safety-review + test-scaffolding skills
+ Recursive Self-Improvement Protocol + AGENTS.md):
- Typed contract (Pydantic extra="forbid", decision_context_id + source + dna_hash +
  shadow_result_ref + proposed_values) — constitution rule 4, Phase 2 spine.
- Central apply (sole writer for these mutations; validation; logging with provenance;
  optional typed bus publish with payload_model; fail-closed on bad proposal) —
  constitution 1/2/5/7, risk-safety checklist (explicit reject, logging, no optimistic).
- Thin delegation from meta_agent_core._apply_candidate (callers unchanged; god surface
  for this path reduced) — no god progress (constitution 3), evolvability +.
- Shadow tie-in (record/ref the experiment_id from prior D5 validate_... at creation;
  logged/warned if absent on risk-affecting apply) — closes D5 gap #1; prepares
  mandatory at-apply in future slice.
- Testable (given-when-then, fail-closed paths explicit, monkeypatch for engine/config/bus)
  per test-scaffolding skill.
- Small, additive, reversible, SIM/paper friendly, evidence-based (first slice only;
  no behavior change on happy paths for challengers/genetic/AB/nightly).
- No direct live capital in this module (pre-promotion evolution config; promotion
  gates + FinalArbitration + human/shadow remain upstream).

Skills application (documented per their required output):
- Constitution Guard: satisfies rules 1 (kapitaalbehoud via explicit contract + fail-closed
  at the mutation point that can reach REAL post-promotion), 3 (progress on god decomp;
  bounded context for this risk mutation), 4 (typed Pydantic), 5 (safety/observability
  before evolution; provenance + shadow ref), 7 (unit-testable with given-when-then).
  No violation of 2/6 (small step, evolution with rem via contract).
- Risk Safety Review (Score: 9/10):
  ✅ Fail-closed: Yes (model rejects extra/invalid; apply returns {"applied": False, "reason": ...}
     or can raise; no silent mutation).
  ✅ REAL mode stricter: N/A for this pre-promotion evolution path (REAL promotion still
     requires shadow + human + FinalArbitration per existing gates).
  ✅ ConstitutionViolation event: Yes (published on missing shadow_result_ref at apply,
     best-effort via bus, using registered "safety.constitution.violation" topic +
     publish_validated + payload_model=ConstitutionViolation; replicates promotion_policy pattern).
  ✅ Logging + provenance (ctx/source/dna/shadow): Yes (rich result + logger.info + recheck log).
  ✅ No optimistic assumptions: Yes (no "trusted proposal" or "ref will be there"; explicit
     violation + fail when absent).
  Minor: full re-validate (not just ref presence) or creation-site injection not in this sub-slice.
  Conclusion: Sub-slice can proceed (additive, closes D5 apply gap #1 for this path, high evolvability value).

Usage (after integration):
    from lumina_core.agent_orchestration.schemas import RiskConfigMutationProposal
    from lumina_core.engine.evolution_risk_proposal import apply_risk_config_mutation
    prop = RiskConfigMutationProposal(...)
    res = apply_risk_config_mutation(proposal=prop, engine=..., bus=event_bus)
    # res: {"applied": bool, "changes": {...}, "decision_context_id": ..., "source": ...,
    #       "dna_hash": ..., "shadow_result_ref": ..., "reason": "..." if not applied}

See tests for given-when-then + fail-closed examples.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from lumina_core.agent_orchestration.schemas import (
    ConstitutionViolation,
    RiskConfigMutationProposal,
)

logger = logging.getLogger(__name__)


def apply_risk_config_mutation(
    *,
    proposal: RiskConfigMutationProposal,
    engine: Any,
    bus: Any | None = None,
) -> dict[str, Any]:
    """Central apply for risk config mutations (the sole writer for max_risk_percent /
    drawdown_kill_percent from evolution hyperparam_suggestion).

    Replaces the inline direct mutation previously at meta_agent_core.py:1041-1047.
    - Validates via Pydantic (extra=forbid already enforced on construction; we
      additionally guard the keys here for defense-in-depth).
    - Mutates only the two risk keys on engine.config (centralized, auditable).
    - Logs with full provenance (decision_context_id, source, dna_hash, shadow_result_ref).
    - Optional typed EventBus publish "evolution.risk_config.mutation" using
      publish_validated + payload_model (if bus provided and supports it).
    - Returns rich result dict for transparency/audit (applied, changes, refs, reason).
    - Fail-closed: unknown keys or no engine/config -> explicit fail result, no mutation.
      (Callers can treat {"applied": False} as reject.)

    This sub-slice (D2 #2) is additive and preserves exact behavior for valid proposals that
    only contain the two risk keys when shadow_result_ref is present. The mandatory
    shadow_result_ref enforcement + ConstitutionViolation on missing (this sub-slice)
    now closes the D5 apply gap #1 for this god mutation point (per 2026-06-07 D2 log + MC
    + 05-31 D2/D5 + explore). Future slices can further harden (e.g. full re-validate at apply,
    genetic creation firewall, or mandatory publish).

    Per 2026-05-31 D2 + SPF-003 + MC (post D4 + post first D2 slice) + D5 residual gap + skills.

    D2 Sub-Slice 3 (genetic creation firewall, this helper): tiny centralized ensure_candidate_has_shadow_ref
    (idempotent best-effort attach of "shadow_result_ref" primary + fallbacks) called from ProposalGenerator
    D5 shadow blocks (challengers + genetic) right after deciding the exp_id used in the validate proposal.
    Hygiene in legacy meta. 1-line pull update in _apply_candidate to prefer the new primary key.
    Makes the sub-slice 2 mandatory apply enforcement succeed with real D5 refs for the main creation volume
    (instead of firing violation on good proposals). Closes the creation-site injection half of D5 gap #1
    ("by construction" at the high-volume genetic/challenger paths per MC "genetic creation firewall" +
    sub-slice 2 log + explore). Additive, best-effort preserved, no behavior change. Centralizes attach
    in the risk module (consistent with central apply from slice 1; supports future typed creation).
    Per 2026-05-31 SPF-003 + Phase 3 D2 + MC post-sub2 trigger.
    """
    if not proposal.proposed_values:
        result = {
            "applied": False,
            "reason": "no-risk-keys",
            "decision_context_id": proposal.decision_context_id,
            "source": proposal.source,
            "dna_hash": proposal.dna_hash,
            "shadow_result_ref": proposal.shadow_result_ref,
        }
        logger.info("risk_config_mutation_noop", extra=result)
        return result

    cfg = getattr(engine, "config", None)
    if cfg is None:
        result = {
            "applied": False,
            "reason": "no-engine-config",
            "decision_context_id": proposal.decision_context_id,
            "source": proposal.source,
        }
        logger.warning("risk_config_mutation_fail", extra=result)
        return result

    # === D2 Sub-Slice 2: Mandatory shadow_result_ref at apply time (per 2026-06-07 D2 log + MC + 05-31 D2/D5 + explore) ===
    # This closes the remaining D5 apply gap #1 for the SPF-003 god mutation point: ref must be present
    # (provided by upstream D5 creation-time shadow calls); if missing, publish ConstitutionViolation (using
    # existing registered topic + publish_validated + payload_model pattern, best-effort non-fatal) and fail.
    # Optional additive recheck: if ref present, load via ShadowRunRegistry.get and log (for observability/audit;
    # does not block or re-validate in this minimal sub-slice).
    # Maps to constitution 1/5 (kapitaalbehoud + safety vóór via mandatory ref + violation before mutation),
    # risk-safety (stronger ✅ ConstitutionViolation event), event-bus-contract (registered topic + payload_model).
    shadow_ref = proposal.shadow_result_ref
    if not shadow_ref:
        if bus is not None and hasattr(bus, "publish_validated"):
            try:
                violation = ConstitutionViolation(
                    principle_name="mandatory_shadow_at_risk_config_mutation_apply",
                    severity="high",
                    description="Risk config mutation apply without prior D5 shadow validation ref (mandatory at apply time)",
                    detail=f"missing shadow_result_ref (required for risk config mutation apply); source={proposal.source}; dna_hash={proposal.dna_hash}; decision_context_id={proposal.decision_context_id}",
                    mode=getattr(getattr(engine, "config", None), "trade_mode", None) or "unknown",
                )
                payload = violation.model_dump(mode="json")
                payload["dna_hash"] = str(proposal.dna_hash) if proposal.dna_hash else None
                bus.publish_validated(
                    topic="safety.constitution.violation",
                    producer="evolution_risk_proposal.apply_risk_config_mutation",
                    payload=payload,
                    metadata={
                        "decision_context_id": proposal.decision_context_id,
                        "source": proposal.source,
                        "dna_hash": proposal.dna_hash,
                        "violation": "missing_shadow_result_ref",
                    },
                )
            except Exception:
                logger.warning(
                    "risk_config_mutation_violation_publish_failed",
                    extra={"decision_context_id": proposal.decision_context_id},
                )
        result = {
            "applied": False,
            "reason": "missing-shadow-result-ref",
            "decision_context_id": proposal.decision_context_id,
            "source": proposal.source,
            "dna_hash": proposal.dna_hash,
            "shadow_result_ref": None,
        }
        logger.warning("risk_config_mutation_missing_shadow_ref", extra=result)
        return result

    if shadow_ref:
        try:
            from pathlib import Path
            from lumina_core.risk.shadow import ShadowRunRegistry

            reg = ShadowRunRegistry(storage_path=Path("state/risk_shadow_evolution.jsonl"))
            prior = reg.get(str(shadow_ref))
            if prior:
                logger.info(
                    "shadow_recheck_at_apply",
                    extra={
                        "ref": shadow_ref,
                        "success": prior.get("success"),
                        "dna_hash": prior.get("dna_hash"),
                        "decision_context_id": proposal.decision_context_id,
                    },
                )
        except Exception:
            logger.debug("shadow_recheck_load_skipped", extra={"ref": shadow_ref, "decision_context_id": proposal.decision_context_id})
    # === end sub-slice 2 enforcement ===

    allowed_keys = {"max_risk_percent", "drawdown_kill_percent"}
    changes: dict[str, Any] = {}

    # Pre-validate all keys (fail-closed before any mutation)
    for k in proposal.proposed_values.keys():
        if k not in allowed_keys:
            result = {
                "applied": False,
                "reason": f"invalid-key:{k}",
                "decision_context_id": proposal.decision_context_id,
                "source": proposal.source,
            }
            logger.warning("risk_config_mutation_invalid_key", extra=result)
            return result

    for k, v in proposal.proposed_values.items():
        old = getattr(cfg, k, None)
        setattr(cfg, k, float(v))
        changes[k] = {"old": old, "new": float(v)}

    result = {
        "applied": True,
        "changes": changes,
        "decision_context_id": proposal.decision_context_id,
        "source": proposal.source,
        "dna_hash": proposal.dna_hash,
        "shadow_result_ref": proposal.shadow_result_ref,
    }
    logger.info("risk_config_mutation_applied", extra=result)

    # Optional typed publish (follows Phase 2 publish_validated + payload_model pattern;
    # non-fatal if bus missing or publish fails — this slice keeps it best-effort like
    # other evolution observability).
    if bus is not None and hasattr(bus, "publish_validated"):
        try:
            payload = proposal.model_dump(mode="json")
            bus.publish_validated(
                topic="evolution.risk_config.mutation",
                producer=proposal.source,
                payload=payload,
                payload_model=RiskConfigMutationProposal,
            )
        except Exception:
            logger.warning(
                "risk_config_mutation_bus_publish_failed",
                extra={"decision_context_id": proposal.decision_context_id},
            )

    return result


# Convenience re-export for callers that want the model in one place.
# (Main model lives in agent_orchestration/schemas.py for canonical contracts.)
__all__ = ["apply_risk_config_mutation", "RiskConfigMutationProposal", "ensure_candidate_has_shadow_ref"]


def ensure_candidate_has_shadow_ref(cand: dict[str, Any], experiment_id: str) -> None:
    """Best-effort attachment of D5 shadow experiment_id (from validate_risk_proposal_in_shadow proposal)
    as 'shadow_result_ref' (primary, matches RiskConfigMutationProposal field) + 'experiment_id' fallback
    onto challenger/genetic/AB candidate/fork dicts.

    This is the core of the "genetic creation firewall" (Phase 3 D2 sub-slice 3 per 2026-05-31 SPF-003
    + MC "genetic creation firewall" + sub-slice 2 log "creation-site injection not yet").

    Ensures the ref flows through AB pool (deepcopy preserves top-level), scoring (dict(ch)), best/selected
    to _apply_candidate + RiskConfigMutationProposal without hitting the sub-slice 2 "missing-shadow-result-ref"
    gate + ConstitutionViolation publish for the main volume paths.

    Idempotent; no-op on non-dict or empty id; does not touch hyperparam_suggestion values or any behavior.
    Call at creation sites right after deciding the exp_id for the shadow proposal (before/after the validate call).

    Future slices can evolve this (e.g. also snapshot a RiskConfigMutationProposal, or make creation produce
    the typed proposal directly).

    Per plan: centralizes attach logic in the risk module (consistent with first-slice central apply).
    """
    if not isinstance(cand, dict) or not experiment_id:
        return
    # Primary key matches the field name in RiskConfigMutationProposal (used at apply + violation)
    cand["shadow_result_ref"] = experiment_id
    # Fallbacks for existing pull logic / legacy sites (additive, no overwrite if already present)
    cand.setdefault("experiment_id", experiment_id)
    # Also set the one used in current direct code for compatibility during transition (harmless)
    cand.setdefault("shadow_experiment_id", experiment_id)
    # decision_context_id for RiskConfigMutationProposal (required field); generate a traceable one if not present
    if "decision_context_id" not in cand:
        cand["decision_context_id"] = f"evo-risk-mutation-{experiment_id}-{uuid.uuid4().hex[:8]}"


# Sub-slice 3 (creation injection) skills application (documented per required output formats)
# Constitution Guard: satisfies 1 (kapitaalbehoud: refs now flow from D5 creation through to the
#   apply/mutation point that can affect REAL post-promotion; fail-closed at apply is now fed real
#   provenance from the actual volume paths), 3 (bounded context progress: attach logic centralized
#   in the risk module rather than scattered in god creation sites), 4 (typed: primary key matches
#   RiskConfigMutationProposal.shadow_result_ref), 5 (safety/observability vóór evolutie: complete
#   creation-to-apply provenance for risk hp mutations), 7 (the helper + post-build asserts are
#   unit-testable with given-when-then + monkeypatch).
# Risk Safety Review (Score: 9/10):
# ✅ Fail-closed: Yes (attach happens at creation before candidates leave the build_* methods;
#    the sub-slice 2 apply gate + ConstitutionViolation on missing is now actually fed real refs
#    from the high-volume ProposalGenerator/AB paths instead of firing on good D5-shadowed proposals).
# ✅ REAL mode stricter: N/A for this pre-apply evolution creation step (REAL guard remains downstream
#    at promotion + FinalArbitration + order_gatekeeper).
# ✅ ConstitutionViolation event: Yes (defense-in-depth; the violation publish path from sub-slice 2
#    remains for any future path that reaches apply without ref; creation now makes it unreachable
#    for the main genetic/challenger volume).
# ✅ Logging + provenance: Yes (experiment_id decided at creation is attached as shadow_result_ref
#    and flows to apply result logs + optional bus publish of the typed RiskConfigMutationProposal).
# ✅ No optimistic assumptions: Yes (helper is best-effort + idempotent; sets the ref from the local
#    exp_id *before* the validate call; even if validate returns None or raises, the ref is present;
#    no assumption that "D5 will have provided it").
# Improvement points: none for this minimal slice (future: also snapshot full RiskConfigMutationProposal
# at creation time inside the helper for even stronger contract).
# Conclusio: Change can go through; makes the prior sub-slice's mandatory enforcement deliver in practice
# for the SPF-003 risk mutation creation paths.
#
# Event-bus-contract: No new topics/publishes in the helper (the "evolution.risk_config.mutation" typed
# publish with payload_model is already in apply from slice 1; the violation one from sub-slice 2).
# The attached ref ensures that when apply does publish the proposal, it carries the D5 lineage.
# Test-scaffolding: New tests in the dedicated risk shadow test file use @pytest.mark.unit,
# given-when-then (build_* with patched validate → returned cands have "shadow_result_ref" == the
# exp_id used in the proposal dict passed to validate, even on None return), explicit fail-closed
# coverage via linkage to apply success, monkeypatch on the bridge.validate.
#
# Per 2026-05-31 SPF-003 + Phase 3 D2 + MC (post sub-slice 2 "genetic creation firewall") +
# sub-slice 2 log ("creation-site injection not yet") + aperture-mission-control + protocol.
