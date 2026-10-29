# ADR-0065: P2 instrument cost bands in $/contract and bp

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Steve (OK 2026-10-29 14:17) + LUMINA Engineering

Addendum to ADR-0055 / ADR-0064. Does not edit ADR-0062, ADR-0063, the
first-cycle pre-register, or holdout seal `85e4588f…`. Does not touch the live
Risk Core fee card.

## Context

Researchers B4: an MNQ tick band is unrealistic because Free-plan commission
alone is $0.94 ≈ 1.88 MNQ ticks. Micros are expensive in dollars; minis have
a richer tick. Steve 14:17: report bands per instrument in $/contract and bp
with the correct ADR-0055 commission.

A second artefact: same-bar round trips (common on MNQ 16/8 versus a wide 1m
range) reported position 0→0, so `apply_costs` skipped both commission sides.
D14 then showed MNQ cost/trade ~10× below MES while MNQ break-even was *higher*
in ticks. That was missing commission, not a cheaper MNQ ticket.

## Decision

1. Bands stay instrument-specific **USD/contract** one-way four-leg windows:
   ES/NQ $3–12, MES $1.50–6.00, MNQ $1.20–5.00. Also report bp vs reference
   notional. Tick conversions are informational, not the band.
2. Commission SSOT remains ADR-0055 Free: MES/MNQ **$0.94/side** ($1.88 RT),
   ES/NQ **$2.87/side** ($5.74 RT). `cost_bands.commission_usd_per_side` checks
   the research contract spec against that card.
3. Same-bar round trips mark the fill bar in-position so the next flat bar
   pays the exit side. Both sides of ADR-0055 commission are charged.
4. Do not retune CostModel coefficients or band edges on holdout or on the
   12/12 kill.

## Consequences

### Positive

- Reports show $/contract and bp next to the commission card, not a fake MNQ
  tick band.
- MNQ 1m scalps no longer look 10× cheaper than MES for the same $0.94 ticket.

### Negative

- ES modeled RTH one-way can still sit above the $12 cap (half-spread 0.5 ES
  ticks is $6.25). That is reported, not retuned.

## Alternatives considered

1. Keep a shared MES/MNQ tick band — rejected (B4).
2. Lower MNQ commission to match the D14 artefact — rejected: the card is $0.94.
3. Fit band edges so ES is in-band — rejected: not a holdout calibration.

## Links

- Note: `experiments/reports/phase5_p2_cost_bands_2026-10-29.md`
- Code: `lumina_research/cycles/cost_bands.py`, `lumina_research/cycles/execution.py`
- Card: `lumina_core/market/nt_fees.py`, ADR-0055
