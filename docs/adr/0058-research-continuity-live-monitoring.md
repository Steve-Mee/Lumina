# ADR-0058: Research continuity and live monitoring (Phase 4)

**Status:** Accepted  
**Date:** 2026-10-28  
**Deciders:** LUMINA Engineering

## Context

Phase 1 put a fail-closed Validation Gate in `lumina_research/validation/`. Phase 2 put a propose-only research loop on the Event Bus. Phase 3 bounded self-evolution so birth and parameter tuning still pass that gate. Steve's Phase 4 goal is that the research layer keeps itself alive: detect live decay against the promotion-time OOS distribution, reduce exposure automatically, cap concentration, scan the Research Charter, and replenish only through the factory.

First principles:

- Capital preservation stays outside the evolutionary path. The live Risk Core (`lumina_core/risk/`) and the packaged research Risk Core / gate floors are not monitoring parameters. Monitoring must not import into `lumina_research/risk_core/` and must not mutate it. Changing those surfaces still requires an ADR plus signed human review (ADR-0057); monitoring never writes them.
- Truth-seeking: live paper/shadow performance is compared to the OOS distribution sealed on `ValidationResult` at promotion, not to in-sample beauty.
- Adaptation rate only counts if decay is retired and new hypotheses still die at the Validation Gate.
- Extreme intellectual honesty, rigorous testing, and radical creativity: the organism may de-weight, suspend, retire, and request new hypotheses; it may not increase exposure or skip the gate.

This supports the mission: a self-evolving research loop that remains fail-closed after promotion.

## Decision

- Continuity lives in `lumina_research/monitoring/`. It does not import `archive/birth-v1/` or `lumina_core/risk/`.
- A live signal may enter the monitoring registry only from a sealed `PromotionCandidate` bound to a MAC-valid `ValidationResult` that independently re-checks gate floors. Direct insertion is refused.
- Live metrics are compared to that signal's OOS distribution over a config-driven rolling window (default 20 trading days) with explicit tests: z-test, empirical percentile, downward CUSUM, and SPRT. Default method `combined` requires two tests to agree before de-weighting (false-alarm control); a single extreme CUSUM may still suspend.
- Stage transitions are monotonic: `active → deweighted → suspended → retired`. Weights only fall (`1.0 → deweight_multiplier → 0`). Restore requires a new gated trial.
- Capacity caps (per signal, instrument, family, correlation cluster) only scale back. Regime information is a size multiplier ≤ 1, never a strategy switch.
- Every positive size still goes through research Risk Core `propose_order()`. Monitoring may only reduce the proposal. Zero-weight signals emit no order.
- `GuardianAgent` runs daily and weekly charter scans (WF windows, CPCV purge+embargo, DSR, PBO promote/reject bands, costs, regimes, Risk Core integrity, promotion-via-gate, trial log). Violations propose suspension only. CLI: `python -m lumina_research.monitoring {daily|weekly}`.
- Replenishment calls `HypothesisAgent` when active count or remaining capacity weight is below a floor. New signals still travel Hypothesis → Validation Gate → Risk Core → `PromotionCandidate`. There is no shortcut into the live registry.
- Additive bus topics: `research.decay.detected`, `research.signal.deweighted`, `research.signal.suspended`, `research.signal.retired`, `research.capacity.scaled`, `research.guardian.finding`, `research.replenishment.requested`. Existing topics stay unchanged. Events are HMAC-sealed and issuer-guarded.
- Every significant decision is appended to the Phase 1/2 experiment JSONL (UTC timestamp, agent_id, full metrics) and, when configured, to the project-brain evolution log directory.

## Consequences

### Positive

- Decayed paper/shadow signals lose exposure without a human in the loop.
- Concentration cannot silently grow past config caps.
- Charter drift is a scheduled, machine-readable scan rather than a hope.
- Replenishment cannot become a skip-gate birth path.

### Negative

- A one-lot signal de-weighted below research Risk Core `min_quantity` is rejected by Risk Core (realized exposure goes to zero). That is fail-closed, not a weight increase.
- Full Phase 1 evaluation still gates every replenishment hypothesis (cost in trials / DSR N).

## Alternatives considered

1. Let the monitor raise weights after a recovery window — rejected: that is an exposure increase without a new Validation Gate pass.
2. Feed live PnL into Risk Core limits — rejected: Risk Core is untouchable; monitoring may only reduce proposals.
3. Reuse `archive/birth-v1/` decay heuristics — rejected: RESEARCH_CHARTER forbids it.
4. Single z-test with no CUSUM — rejected: sequential decay is slower to catch; combined tests keep false alarms bounded.
5. Guardian auto-retires on any warn — rejected: staged reductions; warn ≠ retire. Violations propose suspend.

## Links

- Charter: `RESEARCH_CHARTER.md`
- Phase 1–3: `lumina_research/validation/`, `lumina_research/agents/`, `lumina_research/evolution/`
- Related: `docs/adr/0057-research-self-evolution-within-bounds.md`, `docs/adr/0007-promotion-gate-real-mode.md`
