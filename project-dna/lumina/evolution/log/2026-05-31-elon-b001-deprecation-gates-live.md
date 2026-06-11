# 2026-05-31 — B-001 Deprecation Telemetry Gates Now Live in Daily Guardian

**Context**: The deprecation window for the last remaining mechanism (B-001) is running. To make the hard removal decision objective and impossible to postpone without evidence, the explicit gates have been embedded directly into the daily DNA Guardian report.

**Change made**:
- `scripts/dna_guardian/validate_dna.py` now prints a clear **"B-001 — FINAL DEPRECATION + HARD REMOVAL GATES"** section on every run when the mechanism is in FINAL_DEPRECATION status.
- The section explicitly lists the four non-negotiable gates that must be green before hard removal is allowed.
- This turns the Guardian itself into the primary daily forcing function that tracks when we are permitted to execute the removal.

**Effect**:
- Every Guardian report now contains the current removal readiness status.
- The team can no longer "forget" or softly extend the deprecation window without it being visible in the standard daily output.
- The hard removal proposal is directly referenced in the report.

**Reference documents**:
- Hard removal proposal: `2026-05-31-elon-phase1-3-2-hard-removal-proposal.md`
- Hypothesis: `2026-05-31-elon-phase1-3-2-b001-final-resolution.md`

The measurement layer is now active. The clock on the gates is running visibly.