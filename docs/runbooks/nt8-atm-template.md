# NT8 ATM template — operator steps (ADR-0064 option A)

**Source:** research team decision (relayed by Steve 2026-10-29), 16:36.
Primary protective path is a **server-side NinjaTrader ATM template**.
This file is what CI cannot do. Do it once per broker/connection on PC_Home.

Committed yaml keeps `default_template: ""` and `fallback_companion: true`
so GitHub CI uses option C. Live stays closed.

## Name

Use this exact template name unless you change both NT8 and config together:

`LuminaProtectiveMES`

(MNQ may share the same template if stop ticks are acceptable for both, or
create `LuminaProtectiveMNQ` and map it per instrument later. This PR maps
**per account / connection**, not per instrument.)

## NT8 (PC_Home)

1. Open **NinjaTrader 8**.
2. Control Center → **New** → **ATM Strategy**.
3. Create a new template named **exactly** `LuminaProtectiveMES`.
4. Set:
   - Stop loss: at least as tight as Brain's 1% protective stop on MES
     (operator-chosen ticks; do not leave stop empty).
   - Profit target: optional (research team asked stop+target+OCO; a target
     is allowed).
   - Auto-break-even / trail: optional.
   - Auto reverse: **off**.
5. Save. Confirm the file exists:

`Documents\NinjaTrader 8\templates\AtmStrategy\LuminaProtectiveMES.xml`

6. Chart Trader: select account **Sim101**, instrument **MES**, apply that
   ATM template, place one manual MARKET. Confirm NT shows **ATM child
   stop (and target if configured)** as working orders on the **server**,
   not only a chart drawing.
7. If that manual probe fails on a connection (Playback vs Continuum vs
   Rithmic), leave that connection's template **empty** so Brain uses
   option C for that connection.

## Lumina config (same names)

`%APPDATA%\LUMINA\fabric.json` (host):

```json
"AtmStrategyTemplate": "LuminaProtectiveMES",
"AtmStrategyTemplateByAccount": { "Sim101": "LuminaProtectiveMES" },
"AtmFallbackCompanion": true
```

`config.yaml` (Brain):

```yaml
broker:
  ninjatrader:
    atm:
      default_template: LuminaProtectiveMES
      templates_by_account:
        Sim101: LuminaProtectiveMES
      templates_by_connection: {}
      fallback_companion: true
      companion_confirm_timeout_ms: 5000
```

Restart **NinjaTrader 8** after saving `fabric.json` so the AddOn reloads.

## Probe after restart

1. Keep `research_execution_mode: shadow` until Steve accepts ADR-0064.
2. When SIM is later armed: one MES place via Fabric on Sim101.
3. In NT Control Center / Orders: entry fill plus ATM stop (and target).
4. If ATM child orders are missing after a fill: Brain does **not** retry
   a second MARKET. Flatten the residual on PC_Home (or confirm C attached
   to that live fill). Do not leave an unprotected position.

## Residual (option C)

Companion STOP is a **second** order. MARKET can fill before the STOP is
working. Timeout default 5000 ms, then Risk Core flatten. That race does
not exist when NT ATM attaches stop+target+OCO on the server at entry.
