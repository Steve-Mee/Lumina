# ADR-0060: ResearchBridge SHADOW first (ungated-place freeze)

**Status:** Accepted  
**Date:** 2026-10-28  
**Deciders:** LUMINA Engineering

Numbering note: this record was drafted as ADR-0059 on the S0 branch. Fase 5
landed on `main` first and already occupies ADR-0059 (empirical proof and
Fabric ports). The S0 freeze is unchanged; only the ADR number moved.

## Context

`lumina_research` already publishes sealed `PromotionCandidate` events. KEEP had no consumer of those events. Independently, `supervisor_tick_exec` (and equivalent funnels) could still place SIM/paper/REAL orders on confluence without the Validation Gate. A yaml `mode: sim` or `research_execution_mode` key is not a control: the desk was already in a mode that can submit.

Binding law (integration plan D1–D11): shadow first, zero orders, `expected_horizon` required, ADR-0055 cost SSOT, execution-side wins on discrepancy. Reopening an ungated place requires an ADR plus a human-signed release. This ADR does **not** reopen anything.

First principles:

- Capital preservation: no new risk-increasing order may reach a broker during S0/S1.
- Fail-closed: stale data or a lost connection means no new research signals or intents.
- Honesty: hypothetical fills use the NT Free-plan all-in card and put slippage in the fill price, reported in ticks and dollars, separately for ES/NQ vs MES/MNQ.
- Extreme intellectual honesty, rigorous testing, radical creativity: the freeze is a code tripwire with AST, yaml-flip, and attack tests. The Elon Musk Mindset Protocol applies: do not add a flag that pretends to be a lock.

## Decision

- NEW `lumina_core/order_gatekeeper/ungated_place_block.py` is the S0/S1 tripwire. `assert_validation_gate_or_block` / `gate_order` sit at the start of `place_order`, `execute_order`, `run_tick_exec`, `submit_order`, `submit_order_with_risk_check`, `try_open`, and `submit_paper_order`. Reason code: `UNGATED_PLACE_BLOCKED_S0`.
- Flatten / cancel / emergency reduce remain allowed (`emergency=True` or `reduce_only` that actually reduces live quantity).
- `S0_PLACE_SOURCE_ALLOWLIST` is hardcoded empty and is **never consulted**. Yaml, env, `source_agent="research_bridge"`, and rebinding that set cannot reopen a place. Reopening requires a later ADR plus a human-signed release (not this ADR).
- `research_execution_mode: shadow` in `config.yaml` is observability only (`off|shadow|sim`; missing = off).
- NEW KEEP `lumina_core/research_bridge/` is the first allowed consumer of research events. It verifies HMAC, requires `expected_horizon` (D6; no silent 20 / `oos_size`), logs `SignalIntent` (`strategy_id`, `direction`, `size`, `timestamp`, `expected_horizon` required), and writes hypothetical `FillEvent`s using ADR-0055 commission and one-tick adverse slippage in the fill price (D3). Zero `PlaceOrderCommand`. Zero risk-increasing `place_order`.
- Stale or missing closed bars, or a lost connection: no new SignalIntent, JSONL refuse record, alert.
- Additive bus topics: `research.execution.signal_intent`, `research.execution.order_intent` (`admitted=False`), `research.execution.fill`. Issuer-guarded to `research_bridge` (fills: S2 `fill_translator` also listed).
- `supervisor_tick_exec` stays permanently closed for research signals (D8). S3 must not re-arm confluence auto-place.

## Consequences

### Positive

- SHADOW is actually shadow: research can log and calibrate costs without touching NT/paper/SIM orders.
- The Validation Gate cannot be skipped by confluence, yaml, or env.
- Horizon is an explicit, logged, gated field.

### Negative

- Existing operator/SIM auto-place paths that previously submitted on confluence now return blocked. That is the point of S0. Flatten/emergency still work.
- Default market health for the attached bridge is unhealthy, so production emits no intents until a later phase wires closed-bar health.

## Alternatives considered

1. A yaml `research_execution_mode` switch as the freeze — rejected: D1, a config flag alone is never a control.
2. Leave `supervisor_tick_exec` live and only avoid calling it from research — rejected: D8; confluence remains an ungated place path.
3. Silent default `expected_horizon=20` or copy `oos_size` — rejected: D6.
4. Use the research four-leg `CostModel` as fill SSOT — rejected: D3, execution-side (NT card + fill-price slippage) wins.
5. Gate only `OperationsOrdersMixin.place_order` and hope every caller funnels — rejected: equivalent paths (paper `try_open`, `trade_workers`, reasoning) must be tripwired in the same PR.

## Links

- Plan: `docs/plans/INTEGRATION_PLAN_research_to_nt8.md` (PR #62)
- Cost card: `docs/adr/0055-nt-execution-cost.md`
- Research continuity: `docs/adr/0058-research-continuity-live-monitoring.md`
- Fase 5 empirical proof / Fabric ports: `docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md`
- Charter: `RESEARCH_CHARTER.md`
- Constitution: `project-dna/lumina/constitution.md`
