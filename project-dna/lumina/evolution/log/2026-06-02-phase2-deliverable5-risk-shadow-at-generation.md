# 2026-06-02 — Phase 2 Deliverable 5: Risk Shadow Validation at Candidate Generation Time (MutationPipeline)

**Parent**:
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (original Deliverable 5)
- `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md`

**Status**: Lifecycle coverage progress on Deliverable 5.

---

## Hypothesis

After establishing enforcement at the evaluation gate (ApprovalTwinAgent) and the formal promotion decision gate (PromotionPolicy), the next high-leverage step was to move upstream and add coverage at the **point of experiment creation** — inside the `MutationPipeline`.

By validating risk-related candidates through the shadow aperture at generation time, we ensure that the "must run in shadow" rule begins applying at the earliest stage of a risk-affecting evolution experiment.

---

## What Was Delivered

- Added a best-effort risk shadow validation block inside `MutationPipeline.generate_candidates`, right after the constitutional pre-check.
- Any generated candidate whose content appears to touch risk parameters (max_risk, proposed_risk, drawdown, position sizing, etc.) is now routed through the risk shadow bridge with `auto_record_promotion=True`.
- This creates the third distinct enforcement point in the evolution lifecycle:
  1. Generation time (MutationPipeline)
  2. Evaluation / twin gate (ApprovalTwinAgent)
  3. Formal promotion decision gate (PromotionPolicy)

- Mission Control updated.

- 173 relevant tests remain green.

---

## Measurements vs. Predictions

- ✅ Risk shadow validation now touches the full lifecycle of a risk-affecting evolution experiment.
- ✅ The bridge + auto-record pattern continues to prove reusable at different layers.
- ✅ Still narrow, additive, and low-risk.

---

## Fidelity to Original 2026-05-31 Plan

This slice directly advances the core intent of Deliverable 5 by expanding real enforcement to the point where risk-related DNA variants are first created.

We now have coverage spanning creation → evaluation → promotion. The "every evolution experiment that touches risk logic must run in a shadow aperture mode" requirement is becoming structurally embedded in the evolution machinery.

The remaining work is continuing to make this behavior the automatic default (removing "best-effort" guards) and wiring the engine context more completely into the generation layer.

**Last Updated**: 2026-06-02

Continuing disciplined, evidence-based progress on the capital aperture hardening roadmap.