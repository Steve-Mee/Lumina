# 2026-06-02 — Phase 2 Deliverable 5: First Live Risk Shadow Invocation in Evolution Approval Path

**Parent**:
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (original Deliverable 5)
- `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md`

**Status**: Major milestone — Deliverable 5 moves from "pattern exists" to "actually running in a real evolution gate".

---

## Hypothesis

After building the full isolated risk shadow stack, the bridge, the human review tooling, the promotion automation, and the ergonomic one-call path, the next highest-leverage step was to **make it actually execute** inside the evolution system for risk-affecting proposals.

The ApprovalTwinAgent is a critical, always-on gate for DNA promotion decisions. By wiring the risk shadow bridge into it (when risk_flags are detected), we achieve the first live enforcement of the original requirement:

> "every evolution experiment that touches risk logic must run in a 'shadow aperture' mode"

This is no longer infrastructure — it is now behavior in the approval flow.

---

## What Was Delivered

- Added optional `engine` parameter to `ApprovalTwinAgent`.
- In `evaluate_dna_promotion`, when `risk_flags` are present and an engine is available:
  - Call `run_risk_shadow_experiment_for_proposal(..., auto_record_promotion=True)`
  - Incorporate the shadow recommendation into the twin decision (e.g., force rejection or human review if shadow indicates issues).
  - Best-effort (never breaks the twin).

- Updated the usage documentation in `promotion_policy.py` (previous slice) now reflects real behavior.

- Mission Control updated with honest new evidence ("first live invocation").

- 133+ relevant tests still green.

---

## Measurements vs. Predictions

- ✅ The shadow aperture is now *running* for risky DNA inside a real evolution promotion gate.
- ✅ When risk is flagged, the system automatically exercises the full safe shadow path + promotion recording + potential human review routing.
- ✅ The change is narrow, reversible, and additive.

---

## Fidelity to Original 2026-05-31 Plan

This is the first concrete realization of the "must" in Deliverable 5 inside the live evolution machinery.

We have moved the capability from "excellent library that *could* be used" to "is now being used by default in the approval twin for any DNA that triggers risk flags."

This is the highest-leverage narrow step possible at this stage toward making shadow the non-negotiable path for risk logic evolution.

**Last Updated**: 2026-06-02

Continuing the disciplined execution of the capital aperture hardening roadmap with evidence-based, low-risk increments.