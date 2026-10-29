# ADR-0063: S2.5 NT-PIT tape + S3 gated SIM orders (MES/MNQ)

**Status:** Accepted  
**Date:** 2026-10-29  
**Deciders:** LUMINA Engineering

## Context

S0 (ADR-0060) froze ungated `place_order`. S1 (ADR-0061) added the SIM
whitelist and HMAC `LIVE_RELEASE` while keeping the live account path closed.
S2 (ADR-0062) made `FillEvent` the fill SSOT with ADR-0055 stamps.

Integration plan §3.3.1 and §3.4 (PR #62, D1–D11): S3 may submit research
`OrderIntent`s only after 2–3 **independent NT-PIT** survivors, first on
**MES/MNQ**, through **existing** AdmissionChain + FinalArbitration + NT
broker. Synthetic `materialize()` tapes must not count. `supervisor_tick_exec`
stays permanently closed for research (D8). Research still only **proposes**
alarms; Risk Core `alarm_executor` executes (D7/D9/D10).

Binding law this ADR does **not** reopen: `UNGATED_PLACE_BLOCKED_S0` stays
armed; `live_account_path_closed_s1` stays armed; live orders forbidden; live
Risk Core limits stay untouchable; ADR-0055 is the cost SSOT; holdout pin
`2026-01-28T23:00:00Z` stays closed; `expected_horizon` required.

First principles:

- Capital preservation: S3 is SIM on a whitelist account with
  `sim_real_guard`. REAL HMAC mixed with first SIM is refused.
- Fail-closed: missing corr, synthetic tape, forming bars, look-ahead, ES/NQ
  research orders, stale equity, disconnect, yaml-only `sim` → no place.
- Extreme intellectual honesty, rigorous testing, radical creativity: survivors
  are NT closed bars or they are not survivors. Elon Musk Mindset Protocol: do
  not count two clones or corr ≥ 0.5 as two independents.

## Decision

- NEW `lumina_research/validation/nt_tape.py`: closed NT Last OHLC only.
  Forming bars, look-ahead, vendor-CSV substitutes, and gauss tapes refuse.
  `ValidationResult.tape_kind` defaults to `synthetic` and is HMAC-canonical.
- NEW `sim_gate.py` / `independence.py`: entry criteria 1–9 including D11
  (different hypothesis **and** family **and** corr strictly `< 0.5`).
- NEW `sim_runtime.py`: builds a live `OrderIntent` and calls existing
  `enforce_pre_trade_gate` + broker `submit_order` only inside
  `arm_research_place` after `sim_gate`. No new broker.
- ADAPT `ungated_place_block.py`: allow `source_agent=research_bridge` **only**
  after `sim_gate`. Never consult `S0_PLACE_SOURCE_ALLOWLIST`. Never allow
  `supervisor_tick_exec`.
- ADAPT live `PromotionGate`: `source=research` requires `validation_mac`,
  `report_sha256`, and `tape_kind=nt_pit`. Dictionary-only evidence rejects.
- NEW `lumina_core/risk/alarm_executor.py`: D9 50% / flatten, D10 one retry
  then escalate. Research modules are not on the `submit_order` stack.
- `config.yaml` stays `research_execution_mode: shadow`. Operator restart to
  `sim` is boot-time evidence, not a hot reload.

## Consequences

### Positive

- First research SIM orders cannot skip the Validation Gate or the NT-PIT tape.
- Supervisor confluence still cannot place.
- Alarms execute per strategy_id, not as an account-wide flatten.

**D9 ≡ 6b — research team decision (relayed by Steve 2026-10-29):** there is
no conflict with ADR-0059. Suspend/de-weight = 50% of that strategy;
disable/critical/hard limit = flatten that strategy via Risk Core. Research
still never sends flatten. Hard survivor floor stays **2**; `sim_plan.py`
target is **3**.

### Negative

- No S3 orders until two D11-independent NT-PIT survivors exist on MES/MNQ.
  That is the point.

## Alternatives considered

1. Count Phase 2 planted_edge synthetic survivors — rejected: D2.
2. Re-arm `supervisor_tick_exec` for research — rejected: D8.
3. Execute de-weight inside `lumina_research` — rejected: D7.
4. Open the 2026-01-28 holdout pin for more gate bars — rejected: pin stays closed.
