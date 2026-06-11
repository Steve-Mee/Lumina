# 2026-06-02 — Phase 2 Deliverable 5: Risk Shadow Ergonomics + First Real Usage Pattern

**Parent**:
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md`
- `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md`

**Status**: Usability and integration progress on Deliverable 5.

---

## Hypothesis

After building the capability, the bridge, the human review tooling, and the promotion decision recorder, the next practical step was to make the common case **ergonomic** for evolution callers and to move from "commented example" to a **documented real usage pattern**.

Adding `auto_record_promotion=True` to the main bridge entry point gives callers a simple one-call (or two-call) experience for the majority of risk shadow use cases.

Documenting the pattern in `promotion_policy.py` (beyond a pure comment) starts turning the integration from "available" into "this is how we intend to do it going forward."

---

## What Was Delivered

- `auto_record_promotion: bool = False` parameter added to `run_risk_shadow_experiment_for_proposal`.
  - When True + storage_path provided, the function automatically calls the promotion recorder.
  - This gives a clean one-shot path for many evolution scenarios.

- Improved, actionable usage documentation in `promotion_policy.py` showing the recommended ergonomic pattern with the new flag.

- 1 new focused test for the convenience path.

- Mission Control updated.

- This log entry.

- All tests green (32 relevant tests).

---

## Measurements

- Evolution callers now have a very low-friction way to run risk experiments in shadow and have the promotion outcome automatically committed (including human review routing when needed).
- The documented pattern in the promotion policy file is the first visible "real usage site" guidance.

---

## Fidelity to Original Plan

This slice improves the practicality of the shadow aperture for risk logic changes — directly supporting the goal that such experiments "must run in a shadow aperture mode."

We are steadily moving from "excellent isolated capability" → "usable bridge" → "ergonomic + documented integration pattern."

The remaining gap is scaling this pattern to be the automatic default across more (ideally all) risk-touching mutation sites in the evolution system.

**Last Updated**: 2026-06-02

Continuing the disciplined execution of the 2026-05-31 aperture hardening roadmap.