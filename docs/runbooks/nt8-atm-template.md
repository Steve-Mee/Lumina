# NT8 ATM template — operator steps (ADR-0064 option A)

**Source:** research team 2026-10-29 16:36 (relayed by Steve) and follow-ups
2026-10-29 22:08 (sha256 `991138fd…`) and 23:09 (sha256 `cc904288…`),
research team, **not** Steve.
Primary protective path is a **server-side NinjaTrader ATM template**.
This file is what CI cannot do. Do it **once** on PC_Home for Sim101.

Committed yaml keeps `default_template: ""`, `fallback_companion: true`,
`atm_confirm_timeout_ms: 5000` so GitHub CI uses option C. Live stays closed.

## Probe checklist (PC_Home — preferred, not merge-blocking)

Steve: do this **tomorrow** on **Sim101 only**. Never a live account. Never
`LIVE_RELEASE`. Research team 23:09: preferred before merge, **not blocking**
if local tests + CI are green and the fill-before-ATM residual is documented
(it is, in ADR-0064).

1. NinjaTrader 8 is running. Account selector = **Sim101**. Git `config.yaml`
   still has `research_execution_mode: shadow`. Do not arm SIM for this probe.
2. One ATM template named exactly `LuminaProtective` exists (ATR period 14,
   stop 1.5×ATR, optional target 2.0×ATR, auto reverse off). No per-market copies.
3. `%APPDATA%\LUMINA\fabric.json` has `"AtmStrategyTemplate": "LuminaProtective"`
   and `"AtmStrategyTemplateByAccount": { "Sim101": "LuminaProtective" }`.
   Restart NT8 after saving.
4. Chart Trader, account **Sim101**, instrument **MES**: enable that ATM
   template. Confirm Control Center → Orders shows the ATM child **stop** (and
   target if set) as a **working server order**, not a chart drawing.
5. Repeat step 4 once on **NQ** with the **same** template. Stop distance in
   points must differ from MES (ATR scales). That is the point of one generic
   template.
6. If children are missing after a fill (**fill-before-ATM race**): wait at most
   5s. Do **not** place a second MARKET. Companion STOP may appear; otherwise
   flatten. Log it. This residual is documented and is not a merge blocker.
7. Flatten or cancel the probe fills. Account stays **Sim101**. No live
   account. No real money.

Pass = steps 4–5 show server-side ATM children on MES and NQ. Fail on a
connection = leave that connection's template empty so Brain uses option C.

## Name — one generic template

Use this exact template name. **One** template covers ES, NQ, MES, and MNQ.
Do not create `LuminaProtectiveMES` / `LuminaProtectiveMNQ` / per-market copies.
The 16:36 MES-specific name is **retired**.

`LuminaProtective`

Stops are **ATR multiples**, not market-specific ticks:

| Parameter | Value |
|---|---|
| ATR period | 14 |
| Stop | 1.5 × ATR |
| Profit target (optional) | 2.0 × ATR |
| Auto reverse | off |
| Markets | ES, NQ, MES, MNQ (same template) |

ATR is in that instrument's price units, so one template scales across the four
roots. Tick-based MES vs NQ copies are the failure mode this follow-up forbids.

## NT8 (PC_Home) — Sim101 only for this probe

1. Open **NinjaTrader 8**.
2. Control Center → **New** → **ATM Strategy**.
3. Create a new template named **exactly** `LuminaProtective`.
4. Set:
   - Stop loss: **ATR**, period **14**, multiplier **1.5**. If the ATM editor
     only shows ticks, do **not** invent four tick templates. Use Chart Trader
     ATM stop-strategy type ATR, or a NinjaScript ATM with ATR(14)×1.5. Leave
     the stop non-empty.
   - Profit target: ATR × 2.0 (optional; research team asked stop+target+OCO).
   - Auto-break-even / trail: optional.
   - Auto reverse: **off**.
5. Save. Confirm the file exists:

`Documents\NinjaTrader 8\templates\AtmStrategy\LuminaProtective.xml`

6. Chart Trader: account **Sim101**. Probe **MES** and **NQ** with the **same**
   template. Confirm NT shows **ATM child stop (and target if configured)** as
   working **server** orders, not only a chart drawing. ATR stop distance must
   differ across MES vs NQ (that is the point of one generic template).
7. If that manual probe fails on a connection (Playback vs Continuum vs
   Rithmic), leave that connection's template **empty** so Brain uses
   option C for that connection.

## Lumina config (same names)

`%APPDATA%\LUMINA\fabric.json` (host):

```json
"AtmStrategyTemplate": "LuminaProtective",
"AtmStrategyTemplateByAccount": { "Sim101": "LuminaProtective" },
"AtmFallbackCompanion": true
```

`config.yaml` (Brain) — operator PC_Home overlay; committed git yaml stays empty:

```yaml
broker:
  ninjatrader:
    atm:
      default_template: LuminaProtective
      templates_by_account:
        Sim101: LuminaProtective
      templates_by_connection: {}
      fallback_companion: true
      companion_confirm_timeout_ms: 5000
      atm_confirm_timeout_ms: 5000
```

Restart **NinjaTrader 8** after saving `fabric.json` so the AddOn reloads.

## Probe after restart (same checklist)

Use the **Probe checklist** at the top of this file. Keep
`research_execution_mode: shadow`. When SIM is later armed: one Fabric MARKET
on Sim101 with template `LuminaProtective`. Brain waits at most
`atm_confirm_timeout_ms` (5000). It does **not** retry a second MARKET.
Companion STOP (C) may attach if `fallback_companion` is true. If ATM is still
unconfirmed when the window closes, Risk Core flattens
(`unconfirmed_protective_stop`). Do not leave an unprotected position.

## Residual (option C) — kept

Companion STOP is a **second** order. MARKET can fill before the STOP is
working. Timeout default 5000 ms, then Risk Core flatten. That second-order
race does not exist when NT ATM attaches stop+target+OCO on the server at
entry. The remaining ATM race is fill-before-ATM-children, which this
follow-up closes with the same short window plus flatten.
