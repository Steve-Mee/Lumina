# ADR-0063: P2 positive-control session hold (D13 respec)

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Steve (OK 2026-10-29 12:38) + LUMINA Engineering

Addendum to the P2 research track (ADR-0059, ADR-0062). This file is new. It
does not edit ADR-0062, the first-cycle pre-register, catalog templates, or the
live holdout seal `85e4588f…`.

## Context

D13 requires a planted edge of known size on the real MES/MNQ tape, detected by
the same Validation Gate path, with a shuffled null that must not look like an
edge. The first real-tape step-4 run stopped fail-closed: the implementation
used 1:1 **8/8** brackets and a **16-bar** time-stop. That clips the stated
known size (session RTH open-to-close) into a 1-minute open scalper, so a miss
does not falsify the gate.

C10: RTH filter and session-end flatten (or a time-stop that does not replace
the session hold). C11 (Steve override): no fixed 16/8 floor; geometry is
pre-registered per family. Control geometry is therefore its own pre-register,
not the catalog 16/8.

First principles:

- Extreme intellectual honesty: a control that cannot plant its stated edge is
  theatre. Respec the control to match the known size; do not loosen DSR/PBO.
- Fail-closed: if the respecced control still misses, stop. No further
  geometry iteration without a new OK.
- Elon Musk Mindset Protocol: delete the 8-tick clip instead of adding a second
  control path.
- Capital preservation: research stays propose-only. No Risk Core, PromotionGate,
  S0/S1, or order-path change.

## Decision

1. Pre-register (file
   `experiments/reports/phase5_p2_positive_control_preregister_2026-10-29.md`,
   locked before the rerun):
   - planted sign = session last-RTH-close − first-RTH-open (unadjusted)
   - hold RTH-open to RTH-close via `session_end_flatten=True`
   - `session_filter="rth"`
   - 1:1 `target_ticks = stop_ticks = 20000` (CME 20% limit-move ceiling in
     ticks; not an 8-tick clip)
   - `time_stop_bars = 2000` (cannot fire inside one RTH session)
   - null uses the same geometry; shuffle seed `20261029`
2. Catalog templates and their 16/8 (or family) geometry stay pinned.
3. Holdout pin `2026-01-28T23:00:00Z` and seal `85e4588f…` stay closed. A rerun
   on the same CSVs must not mint a new seal identity.
4. Floors unchanged: DSR >= 0.95, PBO hard 0.50 / warn 0.25.
5. If the planted control is not detected or the null is detected: fail-closed
   `positive_control_failed`, report diagnosis, do not iterate geometry.
6. If the control passes and the null does not: run the 12 first-cycle configs.
   Holdout eval only for independent survivors that already passed the charter
   gate; report, do not promote.

## Consequences

### Positive

- D13 tests session-direction detection instead of 1-minute stop-on-touch noise.
- 1:1 brackets keep the null from becoming a 2R artefact.
- Templates, floors, and the holdout pin remain comparable to the first step-4
  seal.

### Negative

- 20000-tick brackets never exit early, so a gap through the close is booked at
  session flatten (bar close), not at an 8-tick stop. That is the intended
  known size.
- A later Steve OK is required if this control still fails.

## Alternatives considered

1. Keep 8/8 and report only the fail-closed stop — rejected for D13: the
   control did not plant the stated edge.
2. Disable brackets entirely (flatten-only, target/stop unused) — rejected:
   Steve required a pre-registered symmetric 1:1 target/stop.
3. Size brackets from the observed first-RTH-bar range on the failed run —
   rejected: that would tune on the outcome.
4. Loosen DSR/PBO so a weak control can pass — rejected: researchers forbade it.

## Links

- Pre-register: `experiments/reports/phase5_p2_positive_control_preregister_2026-10-29.md`
- Code: `lumina_research/cycles/positive_control.py`
- Related: `docs/adr/0062-static-rule-wfe-replacement.md` (unchanged)
- Charter: `RESEARCH_CHARTER.md`
- Researchers D13, C10, C11: analysis 2026-10-29
