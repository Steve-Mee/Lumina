# ADR-0067: P2 drift-aware multi-seed null (D13)

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Onderzoeksteam advisory 2026-10-29 16:03 (forwarded by Steve; not Steve's opinion) + LUMINA Engineering

Addendum to ADR-0063. This file is new. It does not edit ADR-0063's 20000/20000
session-hold geometry, CostModel 1.2.0, DSR/PBO floors, or holdout seals.

## Context

The NQ D13 null (single permutation, seed `20261029`) kept the session-sign
imbalance. Combined with positive drift, A2 fired on the null (median OOS > 0,
≥60% +OOS) while the planted session-direction edge was real. That is a
method leak, not a market result.

First principles:

- Extreme intellectual honesty: a null that rides drift is not a null.
- Fail-closed: if the redesigned null is still unreliable, stop. No seed
  reroll, no config respec.
- Elon Musk Mindset Protocol: fix the sign-imbalance in the null, do not
  loosen A2 or skip NQ's control.
- Capital preservation: research stays propose-only. Holdout sealed. No orders.

## Decision

1. Pre-register
   `experiments/reports/phase5_p2_multiseed_null_preregister_2026-10-29.md`
   **before** the four-market audit.
2. 32 seeds `20261029 + i`. Per non-overlapping WF partition: detrend session
   OC, shuffle residual signs, balance `|n_pos − n_neg| ≤ 1`.
3. Fail-closed reliability: **ADR-0069 supersedes the majority 16/32 bar.**
   Exact `n_a2/32` is always reported (A2 diagnostic). The cycle stop uses
   calibrated 7/8 false-edge counts (`n_edge`): `≤3/32` reliable, `≥4/32`
   fail (18:17; 4 is fail, not monitor). Planted must beat the median of the
   32 null median-OOS values.
4. Extra only: 8 ISO calendar-week block-shuffles, report-only, never the gate.
5. Same builder on MES, MNQ, ES, NQ. NQ **templates** stay closed until a new
   pre-register is explicitly approved (ADR-0069). Geometry stays 20000/20000.
6. Every seed is a trial. D13 counts.

## Consequences

### Positive

- A drift-heavy tape can no longer clear A2 just by keeping 55% longs.
- The distribution is the result; another reliability bar does not need a
  reroll.

### Negative

- 32 + 8 extra D13 trials inflate N (intended).
- Majority-not-A2 was an engineering lock (Q-NULL-1); ADR-0069 replaces it.

## Alternatives considered

1. Keep single-seed shuffle — rejected: that is the NQ leak.
2. Detrend the evaluation tape instead of the signs — rejected: D13 is a
   sign-shuffle control; changing the score would not test the same gate.
3. Loosen A2 so the old null passes — rejected: researchers forbade floor
   changes.
4. Ask the team before locking 32/10% — rejected for the lock itself (both
   sit inside the written ranges); recorded as open questions.

## Links

- Pre-register: `experiments/reports/phase5_p2_multiseed_null_preregister_2026-10-29.md`
- Advisory: `docs/research/ONDERZOEKERS-ANALYSE-4MARKTEN-20261029T1603.md`
- Code: `lumina_research/cycles/null_model.py`, `positive_control.py`
- Related: `docs/adr/0063-p2-positive-control-session-hold.md`
