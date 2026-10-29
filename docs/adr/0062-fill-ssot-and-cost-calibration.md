# ADR-0062: Fill SSOT, ADR-0055 stamp, monitor observe, per-root calibration (S2)

**Status:** Accepted  
**Date:** 2026-10-29  
**Deciders:** LUMINA Engineering

## Context

S0 (ADR-0060) logs hypothetical ADR-0055 fills. S1 (ADR-0061) keeps SIM
whitelist + HMAC `LIVE_RELEASE` armed and the live account path closed.
Integration plan §3.3 (PR #62, D1–D11): one fill SSOT. Broker fills and S0
hypothetical fills share `FillEvent`. Decay monitor and cost calibrator both
consume that type. Fabric mapper still stamped `commission=0.0`. The live
calibrator mixed roots. Research four-leg cash could disagree with the NT card.

Binding law that this ADR does **not** reopen: `supervisor_tick_exec` stays
closed for research; `UNGATED_PLACE_BLOCKED_S0` stays armed;
`live_account_path_closed_s1` stays armed; live orders forbidden; live Risk
Core limits stay untouchable (research only proposes); `expected_horizon`
required; D9/D10/D11 encoded as proposal-only policy; stale/lost → no new
orders; broker is SSOT; everything logged.

First principles:

- Capital preservation: S2 does not place orders. Hypothetical fills never
  write live calibration.
- Fail-closed: unknown root, missing horizon on a research publish, unmapped
  `strategy_id`, or a research commission below the card is refused.
- Extreme intellectual honesty, rigorous testing, radical creativity: the
  translator is the API; mutating JSONL without `FillEvent` does not observe.
  Elon Musk Mindset Protocol: do not invent a 0.0 commission or a cash
  slippage tick on top of a fill price.

## Decision

- NEW `lumina_core/research_bridge/fill_translator.py` is the fill API.
  `FillEvent` / `ExecutionFill` / reconciler row → `observe(signal_id, metric)`
  **and** live-calibrator JSONL. `strategy_id` from `FillIndex`
  (`client_order_id → strategy_id` + required `expected_horizon ≥ 1`).
  Unmapped fills update desk-level calibration, never a random signal.
- NEW `fill_stamp.py`: Free-plan all-in × qty from `nt_fees` (ADR-0055).
  Slippage = fill vs reference in ticks and dollars when reference is
  present; otherwise omitted (not invented). Execution-side wins on
  discrepancy.
- ADAPT `fabric_mapper.order_event_to_fill`: never leave `commission=0.0`.
  Unknown root → no fill.
- ADAPT reconciler normalize/finalize JSONL: `slippage_ticks`,
  `slippage_usd`, `commission_ticks`, `fill_price`, `qty`, `strategy_id`,
  `source`.
- ADAPT live calibrator: skip `source=hypothetical_adr0055`; group **by
  root** (ES and MES do not share a rolling mean).
- NEW `lumina_research/validation/cost_calibrate.py`: research four-leg
  calibrates *to* the card. Coefficients only tighten. Cannot write
  `state/cost_model_calibration.json`. Isolation: no broker import.
- NEW `binding_policy.py`: D9 50%/flatten, D10 one retry then escalate
  (>10 min), D11 family **and** corr `< 0.5`. Proposal-only. No `place_order`.
- Issuer guard: `fill_translator` may publish `research.execution.fill`
  only. It cannot publish signal/order intents.

## Consequences

### Positive

- Monitor and live calibrator see the same broker `FillEvent`.
- Commission matches the NT Free-plan card per root, in $ and ticks.
- Hypothetical SHADOW fills cannot pollute live calibration.

### Negative

- Fabric fills for unknown roots are dropped rather than recorded at 0.0
  commission. That is fail-closed honesty.
- Research four-leg totals remain estimates beside the card; they must not
  undercut it.

## Alternatives considered

1. Use research four-leg cash as FillEvent commission — rejected: D3,
   execution-side wins.
2. Leave mapper `commission=0.0` and fix it only in the translator —
   rejected: two SSOT numbers.
3. Mix mini and micro in one rolling mean — rejected: D3 separate roots.
4. Calibrate live costs on hypothetical fills — rejected: plan §3.5.
5. Implement S3 `alarm_executor` / SIM orders in this ADR — rejected: S2
   does not place. D9/D10/D11 are encoded as proposal-only policy.

## Links

- Plan: `docs/plans/INTEGRATION_PLAN_research_to_nt8.md` §3.3 (PR #62)
- Cost card: `docs/adr/0055-nt-execution-cost.md`
- S0 freeze: `docs/adr/0060-research-bridge-shadow-first.md`
- S1 whitelist / LIVE_RELEASE: `docs/adr/0061-sim-whitelist-and-live-release.md`
- Charter: `RESEARCH_CHARTER.md`
