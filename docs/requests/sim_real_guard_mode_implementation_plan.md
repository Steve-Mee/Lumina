# SIM_REAL_GUARD Mode Implementation Plan

## 1. Doel

Voeg een nieuwe trade mode toe: `sim_real_guard`.

Functioneel doel:
- Zelfde guard- en runtimegedrag als `real`.
- Zelfde broker-routing type als `sim` (sim-account, geen echt kapitaalrisico).
- Bedoeld als production-parity validatiemodus tussen `sim` (leerpad) en `real`.

Waarom:
- Valideren dat real-gates correct werken zonder echt geld te riskeren.
- Verifiëren of aangeleerde bot-gedragingen robuust zijn onder echte risk/session constraints.

## 2. Harde invarianten (niet onderhandelbaar)

1. Bestaande mode-semantiek blijft intact:
- `paper`: geen broker submit.
- `sim`: leerpad met live market + sim-account, maar risk advisory (niet hard enforced).
- `real`: live market + real-account, hard fail-closed.

2. `sim_real_guard` verandert NIET:
- Core tradingstrategie.
- RL-leermechanisme in `sim`.
- Bestaande route naar `READY_FOR_REAL`.

3. `sim_real_guard` voegt WEL toe:
- Hard risk enforcement (zoals `real`).
- SessionGuard/EOD force-close gedrag (zoals `real`).
- Reconciliation en observability-evidence op real-niveau.

## 3. Nieuwe canonieke mode-matrix

| Eigenschap | paper | sim | sim_real_guard | real |
|---|---|---|---|---|
| Marktdata | intern/gesimuleerd | live | live | live |
| Broker submit | nee | ja (sim-account) | ja (sim-account) | ja (real-account) |
| SessionGuard | nee | ja | ja | ja |
| HardRiskController | nee | advisory | enforced | enforced |
| EOD force-close | nee | nee | ja | ja |
| Kapitaalrisico | geen | geen echt kapitaal | geen echt kapitaal | echt kapitaal |

## 4. Capability-model (centrale bron van waarheid)

Introduceer een capability-resolver in engine-layer (nieuw bestand):
- `lumina_core/engine/mode_capabilities.py`

Aanbevolen API:
- `resolve_mode_capabilities(mode: str) -> ModeCapabilities`

Structuur `ModeCapabilities`:
- `requires_live_broker: bool`
- `risk_enforced: bool`
- `session_guard_enforced: bool`
- `eod_force_close_enabled: bool`
- `reconcile_fills_enabled_default: bool`
- `is_learning_mode: bool`
- `capital_at_risk: bool`
- `account_mode_hint: str`  # paper|sim|real

Doel:
- Geen verspreide `if mode in {"sim", "real"}` checks meer in kritieke paden.
- `sim_real_guard` en `real` delen dezelfde enforcement flags, behalve `capital_at_risk`.

## 5. File-level implementatieplan

### 5.1 Config en mode-validatie

Bestanden:
- `lumina_core/config_loader.py`
- `lumina_core/engine/engine_config.py`
- `lumina_core/engine/agent_policy_gateway.py`

Acties:
1. Mode normalisatie uitbreiden met `sim_real_guard`.
2. Runtime matrix valideren:
- `paper` vereist `broker_backend=paper`.
- `sim`, `sim_real_guard`, `real` vereisen `broker_backend=live`.
3. Secret hygiene:
- `real` blijft strict hard-mode.
- `sim_real_guard` optioneel strict via config-flag, default niet zo streng als real.
4. Policy gateway validatie uitbreiden:
- Geldige modeset: `paper|sim|sim_real_guard|real`.

### 5.2 Gatekeeper en risk/session enforcement

Bestand:
- `lumina_core/order_gatekeeper.py`

Acties:
1. Mode-afhankelijke enforcement vervangen door capabilities.
2. `sim_real_guard` door exact dezelfde session/risk checks als `real`.
3. Bestaande `sim` blijft advisory pad behouden.

### 5.3 Orderpad en operations

Bestand:
- `lumina_core/engine/operations_service.py`

Acties:
1. Mode-semantiek docstring uitbreiden met `sim_real_guard`.
2. Logging uitbreiden met expliciete mode-tags voor parity analyses.
3. Geen wijziging in broker submit flow buiten gates.

### 5.4 Runtime workers en EOD force-close

Bestand:
- `lumina_core/runtime_workers.py`

Acties:
1. `_enforce_real_eod_force_close(...)` refactoren naar capability-check.
2. EOD force-close activeren voor `sim_real_guard` en `real`.
3. Event-codes toevoegen om mode te onderscheiden:
- `EOD_FORCE_CLOSE,mode=sim_real_guard`
- `EOD_FORCE_CLOSE,mode=real`

### 5.5 Broker account intent

Bestanden:
- `lumina_core/bootstrap.py`
- eventueel config docs

Acties:
1. Introduceer expliciete account intent:
- `TRADERLEAGUE_ACCOUNT_MODE=paper|sim|real`
2. Matrix:
- `sim` en `sim_real_guard` moeten account_mode `sim` afdwingen.
- `real` vereist account_mode `real`.
3. Fail-closed bij mismatch.

### 5.6 Reconciliation parity

Bestand:
- `lumina_core/engine/trade_reconciler.py`

Acties:
1. Reconciler startconditie uitbreiden: actief in `sim_real_guard` en `real`.
2. Audit events met mode + account_mode_hint annoteren.

### 5.7 Observability en dashboards

Bestanden:
- `lumina_core/monitoring/observability_service.py`
- `lumina_core/engine/dashboard_service.py`

Acties:
1. Nieuwe metrics:
- `lumina_mode_guard_block_total{mode,reason}`
- `lumina_mode_eod_force_close_total{mode}`
- `lumina_mode_parity_drift_total{baseline="real",candidate="sim_real_guard"}`
2. Dashboardsectie "Mode Parity" met:
- gate reject ratio
- reconciliation delta stats
- force-close events

## 6. Testplan (verplicht)

### 6.1 Unit tests config/gateway

Nieuwe/aan te passen tests:
- `tests/test_mode_capabilities.py` (nieuw)
- `tests/test_order_gatekeeper_contracts.py` (uitbreiden)
- `tests/test_trade_mode_golden_paths.py` (uitbreiden)
- `tests/test_reasoning_service_gateway.py` (uitbreiden)

Cases:
1. `sim_real_guard` is valid trade mode.
2. `sim_real_guard` vereist live broker backend.
3. Policy gateway accepteert mode.
4. Session block in `sim_real_guard` geeft HOLD/block zoals `real`.
5. Risk breach in `sim_real_guard` blockt submit zoals `real`.

### 6.2 Golden paths per mode

Voeg testmatrix toe:
1. `paper`: geen broker calls.
2. `sim`: broker call mogelijk ondanks hard-risk breach scenario (advisory pad blijft).
3. `sim_real_guard`: hard-risk breach blockt.
4. `real`: zelfde block als `sim_real_guard`.

### 6.3 Runtime/EOD tests

Bestand:
- `tests/test_runtime_workers.py`

Cases:
1. EOD force-close triggert in `sim_real_guard`.
2. EOD force-close triggert in `real`.
3. EOD force-close triggert niet in `sim` of `paper`.

### 6.4 Reconciler tests

Bestand:
- `tests/engine/test_trade_reconciler.py`

Cases:
1. Reconciler loopt in `sim_real_guard`.
2. Audit bevat mode-tag en broker_fill_id consistent.

### 6.5 CI Safety Gate

Bestand:
- `.github/workflows/safety-gate.yml`

Acties:
1. Voeg `sim_real_guard` contractsuite toe als release blocker.
2. Fail hard bij mode matrix regressie.

## 7. Rolloutplan

### Fase A - Dark launch
1. Feature flag: `ENABLE_SIM_REAL_GUARD=false` default.
2. Codepad aanwezig, maar mode nog niet operator-selecteerbaar.

### Fase B - Staging
1. Enable in staging.
2. Parallel run:
- `sim` vs `sim_real_guard` op identieke market windows.
3. Verzamel parity evidence:
- block reasons
- reconciliation quality
- latency

### Fase C - Controlled pilot
1. Operator kan mode selecteren.
2. Geen model auto-promotion vanuit `sim_real_guard` zonder extra sign-off.

### Fase D - GA
1. Mode beschikbaar in launcher/docs.
2. Runbook en checklist verplicht ingevuld.

## 8. Acceptatiecriteria

1. Geen regressie op bestaande `paper|sim|real` tests.
2. `sim` behoudt advisory risk behavior.
3. `sim_real_guard` en `real` tonen hetzelfde gategedrag bij gelijke input.
4. EOD force-close werkt in `sim_real_guard`.
5. Reconciler evidence en audittrail zijn aanwezig in `sim_real_guard`.
6. CI bevat expliciete mode-contract regressies.

## 9. Niet-doen (om drift te voorkomen)

1. Geen wijziging van signal generation/strategy logic.
2. Geen wijziging van RL reward/objective in bestaande `sim`.
3. Geen shortcut die `sim_real_guard` dichter bij `sim` maakt qua risk enforcement.

## 10. Aanbevolen implementatievolgorde (commit-batches)

1. Batch 1: mode-capabilities + config/gateway validatie.
2. Batch 2: gatekeeper + operations + runtime workers.
3. Batch 3: reconciler + observability + dashboard labels.
4. Batch 4: tests + safety-gate workflow updates.
5. Batch 5: docs/runbooks + operator checklist.

## 11. Definities voor operators

- `sim`: leren en exploreren, minder hard begrensd.
- `sim_real_guard`: real-regels zonder echt geld, voor production-parity validatie.
- `real`: productie met echt geld.

## 12. Exit criteria voor live-go/no-go

`sim_real_guard` mag pas als representatieve pre-live evidence gelden als:
1. Minimaal 10 opeenvolgende sessies zonder gate/runtime regressie.
2. Reconciliation mismatch-rate binnen afgesproken SLO.
3. Geen kritieke fail-closed incidenten zonder duidelijke root cause.
4. Operator sign-off op parity rapport.
