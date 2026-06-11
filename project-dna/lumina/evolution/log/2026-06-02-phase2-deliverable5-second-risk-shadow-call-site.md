# 2026-06-02 — Phase 2 Deliverable 5: Second Independent Risk Shadow Call Site (PromotionPolicy)

**Parent**:
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (original Deliverable 5)
- `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md`

**Status**: Multi-gate enforcement progress on Deliverable 5.

---

## Hypothesis

After achieving proactive risk shadow validation inside the ApprovalTwinAgent (the main DNA evaluation gate), the next high-leverage step was to add a **second, independent call site** inside the official promotion decision gate (`PromotionPolicy.run_shadow_validation_gate`).

Having coverage at both the "evaluate for promotion" stage and the "formal promotion validation" stage creates redundant, defense-in-depth enforcement of the requirement that risk logic changes must go through the shadow aperture.

---

## What Was Delivered

- Added a small, best-effort risk shadow validation call inside `run_shadow_validation_gate` when risk flags are present.
- This call uses the same bridge + `auto_record_promotion=True` pattern as the twin.
- The official promotion gate now has its own explicit enforcement point for risk-affecting DNA.

- Combined with the proactive twin hook, we now have two independent places in the promotion flow that force risk-relevant proposals through the isolated shadow aperture.

- Mission Control updated.

- All relevant tests (160+) remain green.

---

## Measurements vs. Predictions

- ✅ Risk shadow validation now executes at two distinct points in the evolution promotion pipeline.
- ✅ The pattern (bridge + auto-record) is proven reusable across different parts of the evolution stack.
- ✅ Still narrow, reversible, and non-breaking.

---

## Fidelity to Original 2026-05-31 Plan

This slice directly advances the core of Deliverable 5 by expanding real enforcement from one gate to two gates in the promotion flow.

We are steadily building the "every evolution experiment that touches risk logic must run in shadow" reality inside the actual machinery.

The remaining work is continuing to expand coverage to additional mutation and rollout surfaces until it becomes the non-negotiable default.

**Last Updated**: 2026-06-02

Continuing disciplined, evidence-based progress on the capital aperture hardening roadmap.