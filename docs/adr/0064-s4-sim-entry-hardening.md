# ADR-0064: S4 SIM-entry hardening (continuity meter, D9, protective stops)

**Status:** Accepted  
**Date:** 2026-10-29  
**Deciders:** LUMINA Engineering — Risk Core *apply* of prolonged-disconnect
flatten still **needs human review** (clearly marked proposal). Live stays closed.  
**Source:** research team decision (relayed by Steve 2026-10-29); follow-up
research team 2026-10-29 22:08 sha256 `991138fd…` (**not** Steve); follow-up
research team 2026-10-29 23:09 sha256 `cc904288…` (**not** Steve)

> **Follow-up 22:08 Accepted:** stale equity in `sim` (fail-closed);
> Brain caps-bypass **not approved** (hard caps stay; no silent cap-value
> change). **Follow-up ATM:** one generic ATR template `LuminaProtective` for
> ES/NQ/MES/MNQ; ATM+C kept; hard timeout + Risk Core flatten if ATM is not
> confirmed in the short window (fill-before-ATM race).
>
> **Follow-up 23:09 Accepted:** flatten-grace **hard 5s** (no open-ended);
> prolonged-disconnect flatten at pre-registered **30000 ms**; PC_Home ATM
> probe preferred, **not merge-blocking**. Residual fill-before-ATM race is
> documented and not blocking.
>
> Live stays closed. Risk Core cap *values* remain propose-only. The
> prolonged-disconnect flatten **implementation** in Risk Core is a marked
> proposal pending signed human review before it is live law.

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
- Extreme intellectual honesty: NT `CreateOrder` MARKET may ignore `StopPrice`.
  ATM is wired as option A (template name + StartAtmStrategy). CI cannot prove
  a template exists on PC_Home. Companion STOP (C) is the fallback with a
  documented residual race.
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

### ACCEPTED (research team 22:08, sha 991138fd)

5. **Stale equity blocks new orders in mode `sim`** as well as
   `sim_real_guard` / paper / real. Log + alert. Reduce-only still allowed.
   Fail-closed. **Accepted.**
6. **Caps-bypass is NOT approved.** Close Brain caps-bypass
   `risk_gates.py` `if self.limits.sim_mode or not self.enforce_rules`.
   Remaining advisory path is `enforce_rules=False` only (explicit, logged,
   temporary; tests/paper). `mode_capabilities.sim.risk_enforced=True` so
   desk `sim` actually enforces Brain caps (daily_loss_cap, streak, open-risk).
   This supersedes ADR-0061 “sim stays learning-mode” **for caps only**.
   VaR/ES and MC stay advisory in desk `sim`. Hard VaR/ES/MC remains
   `sim_real_guard` / `real` only. **Cap values are unchanged and remain
   propose-only** — this ADR does not silently retune daily_loss_cap or
   streak numbers. **Accepted: bypass disabled; hard caps stay.**

### ACCEPTED (research team 23:09, sha cc904288)

7. **Flatten-grace hard 5s.** `flatten_grace_ms` / Fabric `FlattenGraceMs` is
   pinned to **5000**. No open-ended grace, no 15s leftover, no 30–60s band.
   After heartbeat timeout, Fabric waits this 5s then flattens only instruments
   this process placed. Fallback in the same window: companion STOP (C) or
   immediate Risk Core flatten. **Accepted.**
8. **Prolonged-disconnect flatten.** Pre-registered threshold
   `prolonged_disconnect_ms: 30000` (approved band 30–60s; **chosen 30s**,
   lower bound, fail-closed). On reconnect, if the disconnect lasted ≥ 30000 ms
   **and** the strategy has no confirmed server-side stop (ATM or companion),
   Risk Core flattens via D9 stage `prolonged_disconnect`. Unknown stop status
   fail-closes to flatten. Confirmed ATM/C skip flatten (the stop is already on
   NT). Code: `lumina_core/risk/prolonged_disconnect.py` plus
   `AlarmExecutor.maybe_flatten_after_disconnect`. **Policy Accepted.
   Risk Core apply is a marked proposal and still needs human review.**
9. **Protective stops — A default, C fallback.**
   Research team decision (relayed by Steve 2026-10-29, 16:36) plus follow-up
   22:08 (sha 991138fd):
   - **Primary A:** **one** generic ATR-based NT ATM template named
     `LuminaProtective` for ES/NQ/MES/MNQ (stops in ATR multiples: period 14,
     stop 1.5×ATR, optional target 2.0×ATR). Fabric proto field
     `atm_strategy_template`. Operator sets this **once** on Sim101. The
     16:36 name `LuminaProtectiveMES` is retired. Per-connection empty string
     still disables A for that connection (C fallback).
   - **Fallback C:** companion protected STOP when ATM is missing or
     unconfirmed for that broker/connection. Residual: MARKET may fill
     before STOP is working. Hard timeout (default 5000 ms) then Risk Core
     flatten (`unconfirmed_protective_stop`). **Kept.**
   - **Residual fill-before-ATM race (documented, not merge-blocking):**
     NT `Submit` then `StartAtmStrategy` can fill the MARKET before ATM
     children are working. Same 5s window as flatten-grace /
     `atm_confirm_timeout_ms`. Brain does not retry a second MARKET. C may
     attach; if ATM is still unconfirmed when the window closes, Risk Core
     flattens. This residual is honest NT behaviour, not a blocker.
   - **ATM confirm window:** `atm_confirm_timeout_ms` (default 5000). If ATM
     is not confirmed in that short window after a fill (**fill-before-ATM
     race**), Brain may attach C; if C is off or also unconfirmed, Risk Core
     flattens. Gateway must not hide a fill behind a clean ATM reject
     (`atm_unconfirmed_after_fill`).
   - **Fail-closed:** no new entry if neither ATM nor a confirmed C-stop.
     ATM reject does **not** retry a second MARKET (a silent NT fill plus
     a retry would double).
   - **Not B** (raw `CreateOrder` OCO id) and **not D** (stop-market as
     primary).
   - Brain still refuses risk-increasing `sim_real_guard`/`real` places
     without `stop_price`. C# gateways reject the same.

### Operator NT8 work that CI cannot prove (option A)

ATM templates live inside NinjaTrader on PC_Home. This PR wires the name,
attach call, and fail-closed fallback. It does **not** create the template
file. Exact operator steps: [`docs/runbooks/nt8-atm-template.md`](../runbooks/nt8-atm-template.md).

What this repo proves in SIM/CI:
- Proto round-trip of `atm_strategy_template` / `protective_attach`
- Path selection: template present → A; empty/unreliable → C; neither → refuse
- SimOrderGateway attaches a simulated ATM child stop, or rejects
  `atm_unavailable` without a fill, or (CI) fills without ATM children
- Companion confirm timeout → flatten
- ATM confirm timeout / fill-before-ATM → companion or Risk Core flatten
- NtAccountOrderGateway calls `AtmStrategy.StartAtmStrategy` by reflection
  when NinjaTrader.Core is present; standalone CI build reports
  `atm_api_unavailable`. If StartAtmStrategy fails after Submit and the
  MARKET already filled, the AddOn returns the fill with
  `atm_unconfirmed_after_fill` (does not hide it behind a clean reject).
  Brain does not retry a second MARKET; it flattens if ATM is still
  unconfirmed when the short window closes. CI cannot prove the live NT
  template file on PC_Home.

What Steve/operator must do on PC_Home (not automatable here):
1. Create **one** ATM template named exactly `LuminaProtective` (ATR 14,
   stop 1.5×ATR) for ES/NQ/MES/MNQ. Probe Sim101 with MES **and** NQ.
2. Write that name into `%APPDATA%\LUMINA\fabric.json` and
   `config.yaml` `broker.ninjatrader.atm.templates_by_account`.
3. Restart NT8 so the AddOn reloads Fabric config.
4. One operator SIM probe: confirm ATM child stop+target appear on Sim101
   after a Fabric MARKET. Until that probe, C fallback is the honest path.

## Consequences

### Positive

- SIM entry FAR/TTD/power cannot be a JSON float.
- D9 and original 6b are one table.
- Unprotected `sim_real_guard` entries are refused even if NT ignores StopPrice on MARKET.
- ATM template is the default protective path when the operator has created it.

### Negative

- Desk `sim` is cap-enforcing (Accepted 22:08; learning-mode tests use the explicit `enforce_rules=False` advisory).
- Daily NT-PIT tape is required before first SIM; 1m 241-bar fixture is not TTD evidence.
- Companion STOP (C) still has a fill-before-stop race; flatten is the backup, not ATM.
- Fill-before-ATM is a residual race (5s then C or flatten). Documented; not merge-blocking.
- ATM attach is not proven in GitHub CI (no NT8 process / template file). PC_Home probe is preferred, not blocking.
- Prolonged-disconnect flatten is Accepted policy; Risk Core apply still **needs human review**.

## Alternatives considered

1. Keep caller `far_healthy: float` and only lower the floor to 0.10 — rejected: invented evidence.
2. Raise the gate to 3 survivors — rejected: 3 is the target, 2 is the hard min.
3. Change D9 to “alarm never flattens” as original ADR-0059 table — rejected: research team chose D9; 6b is the same mapping.
4. Claim NT MARKET StopPrice is a server-side protective stop — rejected: honesty.
5. Option B (raw OCO id on `CreateOrder`) — rejected by research team 16:36.
6. Option D (stop-market as primary entry) — rejected by research team 16:36.

## Follow-up 2026-10-29 22:08 (sha 991138fd)

Frozen answers: [`docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md`](../research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md).

**Risk Core proposal (not silently applied):** do not retune `daily_loss_cap`,
streak, or open-risk numbers in this follow-up. The only Risk Core *behavior*
changes already on `main` from S4 (stale equity in `sim`; close `sim_mode`
caps short-circuit) are now Accepted. Any future cap-value change needs its
own ADR + signed human review.

## Follow-up 2026-10-29 23:09 (sha cc904288)

Frozen answers: [`docs/research/ONDERZOEKERS-ANTWOORDEN-S4-PR73-20261029T2309.md`](../research/ONDERZOEKERS-ANTWOORDEN-S4-PR73-20261029T2309.md).

Chosen disconnect threshold: **30000 ms**. Flatten-grace: **5000 ms** hard.

**Risk Core proposal (not silently applied):** `maybe_flatten_after_disconnect`
is the reconnect flatten. Do not treat it as live law until signed human
review. Cap values still unchanged.

## Links

- Decisions: research team (relayed by Steve 2026-10-29); follow-up research team 2026-10-29 22:08 sha 991138fd (not Steve); follow-up research team 2026-10-29 23:09 sha cc904288 (not Steve)
- Prior: `docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md`, `docs/adr/0063-sim-orders-gated.md`, `docs/adr/0043-telegram-io-ssot.md`
- Code: `lumina_core/research_bridge/continuity_meter.py`, `sim_gate.py`, `protective_stop.py`, `protective_attach.py`, `alerts.py`
- Risk Core: `lumina_core/risk/risk_gates.py`, `lumina_core/engine/mode_capabilities.py`, `lumina_core/order_gatekeeper/engine_helpers.py`, `lumina_core/risk/alarm_executor.py`
- Operator ATM: [`docs/runbooks/nt8-atm-template.md`](../runbooks/nt8-atm-template.md)
