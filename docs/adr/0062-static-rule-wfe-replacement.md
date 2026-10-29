# ADR-0062: Static-rule WFE replacement (A2) and CPCV skip (A3)

**Status:** Proposed
**Date:** 2026-10-29
**Deciders:** LUMINA Engineering

## Context

P2 templates are pre-registered static rules. There is no in-window fit, grid, or
parameter search. Walk-forward still splits the train tape into IS/OOS windows,
but WFE (OOS Sharpe / IS Sharpe) is undefined when IS Sharpe is structurally
negative, and CPCV reconstructs the same path on every combinatorial fold.

Researchers (2026-10-29 A2/A3): for static rules replace the WFE *requirement*
with (a) median OOS after costs > 0, (b) share of positive OOS windows >= 60%,
(c) a stability test with no structural decay. CPCV only when a real fit step
exists; otherwise use the walk-forward OOS distribution plus a block-bootstrap.

First principles:

- Extreme intellectual honesty: an empty WFE/CPCV cell is not a pass and not a
  reason to loosen DSR or PBO.
- Fail-closed: missing OOS windows, missing costs, missing market regimes, or
  doubt still reject.
- Elon Musk Mindset Protocol: do not keep a metric that cannot be computed; replace
  it with tests that actually constrain static rules.
- Capital preservation: research stays propose-only. This ADR does not touch the
  live Risk Core, PromotionGate, or S0 freeze. DSR >= 0.95 and PBO hard 0.50 /
  warn 0.25 stay packaged floors.

## Decision

1. `ValidationResults.has_fit_step` is True by default (Phase 1/2 candidates that
   still run CPCV + WFE). P2 catalog specs set `has_fit_step=False`.
2. When `has_fit_step` is False:
   - WFE is recorded as NaN with `WFESnapshot.mode == "static_rules"`.
   - `missing_or_undefined_wfe` and `wfe_below_threshold` do **not** fire.
   - Gate instead requires `static_rules` mode, median OOS > 0
     (`static_median_oos_not_positive` when median <= 0; `negative_median_oos_after_costs`
     still fires when median < 0), `oos_distribution.pct_positive >= 0.60`
     (`static_positive_share_below_60`), and
     `parameter_stability >= 0.5` (`static_structural_decay`; non-finite stability is decay).
   - Structural decay is Spearman ρ of OOS window means vs time; ρ < -0.50 fails.
     Fewer than 6 finite windows is fail-closed decay.
   - CPCV is not run. The gate OOS distribution is the walk-forward OOS window
     means. A moving-block bootstrap of daily/bar net returns is stored as
     diagnostics, not as a second gate.
3. When `has_fit_step` is True, CPCV + WFE floors are unchanged.
4. DSR and PBO floors are unchanged. This ADR does not lower them.
5. Fitness for `mode == "static_rules"` uses `parameter_stability` in place of
   the WFE term so a NaN WFE cannot smuggle a skip.

## Consequences

### Positive

- Static P2 templates are judged on OOS sign, hit-rate of windows, and decay,
  which are defined even when IS Sharpe is negative.
- CPCV is reserved for real search, so it cannot look informative while being
  degenerate.

### Negative

- A static rule can no longer be killed solely for undefined WFE. It can still
  be killed for negative median OOS, <60% positive windows, decay, DSR, PBO,
  missing costs, or missing market regimes.
- Block-bootstrap is diagnostic, not a hard floor. Reviewers must not treat it
  as CPCV.

## Alternatives considered

1. Keep WFE as a hard floor for static rules — rejected: undefined on the P2
   tape, so every template dies for an artefact, not the hypothesis.
2. Treat identical CPCV paths as a pass — rejected: that is theatre.
3. Loosen DSR/PBO to let static rules survive — rejected: researchers forbade it.

## Links

- Researchers A2/A3: uploaded analysis 2026-10-29
- Code: `lumina_research/validation/static_rules.py`, `gate.py`, `pipeline.py`,
  `block_bootstrap.py`
- Charter: `RESEARCH_CHARTER.md`
- Related: `docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md`
- Numbering: ADR-0061 is S1 SIM whitelist / LIVE_RELEASE. This decision is 0062.
