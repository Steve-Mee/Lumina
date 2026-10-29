# ADR-0064: S4 SIM-entry hardening (continuity meter, D9, protective stops)

**Status:** Proposed  
**Date:** 2026-10-29  
**Deciders:** LUMINA Engineering — **needs human review**  
**Source:** research team decision (relayed by Steve 2026-10-29)

> **NEEDS HUMAN REVIEW.** Risk Core edits in this PR (Brain caps-bypass,
> stale equity in `sim`, prolonged-disconnect flatten, flatten-grace clamp)
> are Proposed, not Accepted. Do not merge as live law. Live stays closed.

## Context

S0–S3 are on `main` (`58971dc`). A gap-audit of items 4–6 found: caller-supplied
FAR floats in `sim_gate`, `sim_plan` min 3 vs gate min 2, Brain `check_can_trade`
short-circuit when `limits.sim_mode`, stale equity not required in desk `sim`,
no Telegram sink for research/alarm rejects, 15s flatten-grace, and no
enforceable server-side stop on NT MARKET.

Five research-team decisions (relayed by Steve 2026-10-29) plus two audit
leftovers (caps-bypass, Telegram 6c) are the S4 scope. First principles:

- Capital preservation: SIM entry cannot proceed on invented FAR/TTD/power.
- Fail-closed: missing meter, missing stop, stale equity, prolonged disconnect
  without flatten → no new risk.
- Extreme intellectual honesty: NT `CreateOrder` MARKET may ignore `StopPrice`;
  native ATM/OCO is not implemented. Do not pretend it is.
- Elon Musk Mindset Protocol: D9 already matches 6b; document that instead of
  forking a second mapping.

## Decision

### KEEP (research / Fabric / docs)

1. **D9 = 6b (no conflict).** Disable / critical / hard limit → flatten that
   strategy. Suspend / de-weight → 50%. Research still never sends flatten.
   Documented in ADR-0059 and ADR-0063.
2. **Min 2 independent survivors is the hard gate.** `sim_plan.py` target is 3
   (`SIM_TARGET_SURVIVORS`). Gate stays `MIN_SURVIVORS = 2`.
3. **Continuity meter is the only SIM-entry FAR/TTD/power source.**
   `lumina_core/research_bridge/continuity_meter.py` reads NT-PIT `ClosedBar`
   only. Floors: FAR ≤ 10%, TTD fast ≤ 15d, TTD slow ≤ 45d, power ≥ 85%.
   Planted decay is a mean-shift on those NT returns (not gauss prices).
   Daily-spaced tape required for TTD-in-days. `sim_gate` rejects raw floats
   and missing reports.
4. **TelegramAlertSink (6c)** journals via ADR-0043. No credentials →
   `drop_reason=no_credentials`. No second poller. No network in tests.

### PROPOSE — Risk Core / Fabric (**needs human review**)

5. **Stale equity blocks new orders in mode `sim`** as well as
   `sim_real_guard` / paper / real. Log + alert. Reduce-only still allowed.
6. **Close Brain caps-bypass** `risk_gates.py` `if self.limits.sim_mode or not
   self.enforce_rules`. Remaining advisory path is `enforce_rules=False` only.
   `mode_capabilities.sim.risk_enforced=True` so desk `sim` actually enforces
   Brain caps (daily_loss_cap, streak, open-risk). This supersedes ADR-0061
   “sim stays learning-mode” **for caps only**. VaR/ES and MC stay advisory
   in desk `sim` (allocator `_var_es_enforcement_enabled` /
   `_mc_enforcement_enabled` already return False for mode `sim`; the
   admission gate must match and must not key those two checks off
   `capabilities.risk_enforced`). Hard VaR/ES/MC remains `sim_real_guard`
   / `real` only.
7. **Flatten-grace backup 30–60s** (chosen 30000 ms, clamp `[30000, 60000]`).
8. **Prolonged disconnect:** on reconnect, AlarmExecutor reconciles with broker
   as SoT then flattens open strategy qty via D9 stage `prolonged_disconnect`.
9. **Protective stops — enforceable subset only.**
   - Brain refuses risk-increasing `sim_real_guard`/`real` places without
     `stop_price`.
   - C# `NtAccountOrderGateway` / `SimOrderGateway` reject the same when
     `ModeContext` is `sim_real_guard` or `real`.
   - After accepted MARKET, Brain submits a companion `STOP` with
     `protected=true` (CancelNonProtected must not cancel it).

### STOPPED — NT native ATM/OCO

NinjaTrader `CreateOrder(..., stop, oco="", ...)` for `OrderType.Market` does
not attach a native ATM strategy. Options (not in this PR):

| Option | What it is | Why not now |
|---|---|---|
| A. NT ATM template | Broker-native stop/target strategy | No ATM name in Fabric proto; per-broker templates undocumented |
| B. OCO group | `CreateOrder` oco id linking entry+stop | Currently `string.Empty`; needs proto + NT OCO lifecycle |
| C. Companion STOP (this PR) | Second order, `protected=true` | Enforceable; stop can miss if companion reject is ignored — fail-closed on that reject |
| D. Stop-market as primary | Replace MARKET entries | Changes fill semantics vs current SIM plan |

## Consequences

### Positive

- SIM entry FAR/TTD/power cannot be a JSON float.
- D9 and original 6b are one table.
- Unprotected `sim_real_guard` entries are refused even if NT ignores StopPrice on MARKET.

### Negative

- Desk `sim` becomes cap-enforcing (**needs human review** — learning-mode tests change).
- Daily NT-PIT tape is required before first SIM; 1m 241-bar fixture is not TTD evidence.
- Companion STOP is not ATM; option A/B remains open.

## Alternatives considered

1. Keep caller `far_healthy: float` and only lower the floor to 0.10 — rejected: invented evidence.
2. Raise the gate to 3 survivors — rejected: 3 is the target, 2 is the hard min.
3. Change D9 to “alarm never flattens” as original ADR-0059 table — rejected: research team chose D9; 6b is the same mapping.
4. Claim NT MARKET StopPrice is a server-side protective stop — rejected: honesty; STOPPED with options A–D.

## Links

- Decisions: research team (relayed by Steve 2026-10-29)
- Prior: `docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md`, `docs/adr/0063-sim-orders-gated.md`, `docs/adr/0043-telegram-io-ssot.md`
- Code: `lumina_core/research_bridge/continuity_meter.py`, `sim_gate.py`, `protective_stop.py`, `alerts.py`
- Risk Core (Proposed): `lumina_core/risk/risk_gates.py`, `lumina_core/engine/mode_capabilities.py`, `lumina_core/order_gatekeeper/engine_helpers.py`, `lumina_core/risk/alarm_executor.py`
