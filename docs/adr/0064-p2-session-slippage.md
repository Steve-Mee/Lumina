# ADR-0064: P2 RTH/ETH session slippage

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** Steve (OK 2026-10-29 14:17) + LUMINA Engineering

Addendum to the P2 research track (ADR-0055, ADR-0059). This file is new. It
does not edit ADR-0062, ADR-0063, the first-cycle pre-register, catalog
templates, or the live holdout seal `85e4588f…`.

## Context

Researchers B5: slippage that is purely inverse-volume with a fixed
`volatility_price=2.0` punishes ETH. CostModel 1.1.0 already replaced the
fixed 2.0 with bar true-range, but ADV was still a mixed 21-bar window.
Overnight volume against the cash-open ADV inflated `1/volume_ratio` and made
ETH look several times more expensive than RTH for the same true range.

First principles:

- Extreme intellectual honesty: a session-agnostic ADV is not a liquidity
  model. Split the denominator.
- Fail-closed: do not fit ETH coefficients on the P2 OOS or the sealed holdout.
- Elon Musk Mindset Protocol: delete the mixed-window artefact instead of
  adding a fudge factor after seeing kills.
- Capital preservation: research stays propose-only. No Risk Core, no orders.

## Decision

1. CostModel **1.2.0**: slippage coefficient is looked up per `MarketSnapshot.session`
   (`rth` or `eth`). Vol term remains bar true-range / tick.
2. Tape ADV is `causal_session_adv`: last 21 bars of the **same** session type.
3. Inverse-volume scale is capped at 4. A dead bar cannot explode.
4. Documented table (no SIM fills in-repo): RTH 0.10, ETH 0.10. Both knobs are
   explicit. They are not fit on this tape. See
   `experiments/reports/phase5_p2_slippage_rth_eth_2026-10-29.md`.
5. ADR-0055 commission card is unchanged. This ADR does not retune DSR/PBO.

## Consequences

### Positive

- ETH bars are costed against ETH liquidity.
- The vol term stays; the 2.0 constant stays deleted.

### Negative

- Without SIM fills the ETH coefficient equals RTH. Overnight *spreads* may
  still be understated (half-spread stays 0.5 ticks). A later OK is required
  to change coefficients from fills.
- Existing MES/MNQ reports (CostModel 1.1.0) stay as the pre-fix baseline.
  A cost-fix rerun writes new files.

## Alternatives considered

1. Lower the ETH coefficient after seeing 12/12 kill — rejected: outcome tuning.
2. Keep mixed ADV and only cap `1/volume_ratio` — rejected: still compares ETH
   to RTH liquidity.
3. Calibrate on holdout or on the sealed MES/MNQ train OOS — rejected: pin closed.

## Links

- Note: `experiments/reports/phase5_p2_slippage_rth_eth_2026-10-29.md`
- Code: `lumina_research/validation/cost_model.py`, `lumina_research/cycles/execution.py`,
  `lumina_research/cycles/slippage_calibration.py`
- Charter: `RESEARCH_CHARTER.md`
- Researchers B5: analysis 2026-10-29
