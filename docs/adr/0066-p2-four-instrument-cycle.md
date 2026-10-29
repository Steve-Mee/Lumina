# ADR-0066: P2 four-instrument cycle after cost fix

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Steve (OK 2026-10-29 14:13 and 14:17) + LUMINA Engineering

Addendum to ADR-0059 / 0063 / 0064 / 0065. This file is new. It does not edit
those ADRs, the 24-variant catalog, `phase5_first_cycle_preregister.md`, or
seal `85e4588f…`.

## Context

Steve asked to translate the locked 12 families onto ES/NQ because full-size
tick value is 10× the micro (ES $12.50 vs MES $1.25; NQ $5 vs MNQ $0.50) while
ADR-0055 commission does not scale 10×. Researchers F18 allowed ES/NQ only
after the cost artefacts were fixed. 14:17 required CostModel 1.2.0 and
$/contract bands **before** this pre-register.

The catalog already has ES/NQ duplicates with **different** lookbacks and 8/4
geometry. Running those would confound the cost comparison. This cycle copies
the first-cycle lookback/threshold/16/8 onto ES/NQ under new `p2c-*` ids.

First principles:

- Extreme intellectual honesty: same mechanism, same tick geometry, different
  contract. Do not quietly switch to 8/4.
- Fail-closed: no tape, non-PIT tape, or failed D13 control → stop that
  instrument. No geometry iteration without a new OK.
- Capital preservation: propose-only. Holdout stays sealed. No Risk Core.

## Decision

1. Pre-register in
   `experiments/reports/phase5_p2_four_instrument_preregister_2026-10-29.md`
   **before any rerun**.
2. Rerun the original 12 MES/MNQ configs with CostModel 1.2.0 into **new**
   report files. Keep the 1.1.0 `phase5_p2_results.md` as baseline.
3. Run the 12 `p2c-*` ES/NQ translations the same way, D13 control per
   instrument (20000/20000 session hold).
4. Reuse MES/MNQ seal `85e4588f`. New ES/NQ seal file at pin
   `2026-01-28T23:00:00Z` if PIT tapes exist.
5. Floors unchanged: DSR 0.95, PBO 0.50. No promotion.

## Consequences

### Positive

- Cost-fix effect on MES/MNQ is visible next to the frozen 1.1.0 table.
- ES/NQ comparison uses the same 16-tick target, so dollar edge vs dollar
  ticket is not confounded by a smaller mini geometry.

### Negative

- Catalog 8/4 ES/NQ rows remain unused. A later cycle can run them under
  their own pre-register.
- No ES/NQ zip in this workspace at pre-register time is a fail-closed data
  gap, not a reason to synthesize bars.

## Alternatives considered

1. Run the deferred catalog ES/NQ 8/4 rows — rejected: different geometry.
2. Overwrite `phase5_p2_results.md` with the cost-fix rerun — rejected: lose
   the 1.1.0 baseline.
3. One combined 24-config trial count for DSR — rejected for this cycle:
   MES/MNQ cost-fix and ES/NQ translation are reported as two batches; DSR
   still sees the registry of that batch.

## Links

- Pre-register: `experiments/reports/phase5_p2_four_instrument_preregister_2026-10-29.md`
- Costs: ADR-0064, ADR-0065, ADR-0055
- Control: ADR-0063
- Charter: `RESEARCH_CHARTER.md`
