# SIM_REAL_GUARD Mode Implementation TODO List

## Doel
- Nieuwe mode `sim_real_guard` implementeren als real-parity validatiemodus op sim-account.
- Bestaande mode-semantiek van `paper`, `sim`, `real` blijft ongewijzigd.
- Geen wijziging van tradingstrategie of RL-leerdoel in bestaande `sim` flow.

## Planning met prioriteit en ETA

| Blok | Prioriteit | ETA | Doeluitkomst |
|---|---|---|---|
| Fase 1 - Foundation | P0 | 2 werkdagen | Mode/capabilities en matrix-validatie stabiel |
| Fase 2 - Gates + Orderpad | P0 | 3 werkdagen | `sim_real_guard` gategedrag parity met `real` |
| Fase 3 - Runtime Parity | P0 | 2 werkdagen | EOD + reconciler parity operationeel |
| Fase 4 - Observability | P1 | 2 werkdagen | Parity metrics en dashboard zichtbaarheid |
| Fase 5 - CI + Docs | P0 | 2 werkdagen | Release-blocking contracts en operator docs |
| Rollout A - Dark launch | P0 | 1 werkdag | Feature flag aanwezig, mode afgeschermd |
| Rollout B - Staging parallel run | P0 | 5 handelsdagen | Parity evidence set compleet |
| Rollout C - Controlled pilot | P1 | 3 handelsdagen | Operator-gestuurde pilot zonder regressie |
| Rollout D - GA | P1 | 1 werkdag | Formele vrijgave inclusief sign-off |

## Doelplanning (kalender)

- Startdatum: 2026-04-16
- Streefdatum technisch gereed (Fase 1 t/m 5): 2026-04-27
- Streefdatum rollout gereed (A t/m D): 2026-05-08

## Harde randvoorwaarden (altijd valideren)
- [ ] `paper` blijft zonder broker-submit.
- [ ] `sim` blijft advisory risk mode (`enforce_rules=False` gedrag blijft intact).
- [ ] `real` blijft fail-closed met volledige enforcement.
- [ ] `sim_real_guard` krijgt dezelfde gates als `real`, maar zonder echt kapitaalrisico.
- [ ] Geen strategy/RL drift door deze wijziging.

## Fase 1 - Mode foundation en capability-resolver

- Prioriteit: P0
- ETA: 2 werkdagen

### 1.1 Nieuwe capabilitylaag toevoegen
- [x] Nieuw bestand toevoegen: `lumina_core/engine/mode_capabilities.py`.
- [x] `ModeCapabilities` model toevoegen met velden:
  - [x] `requires_live_broker`
  - [x] `risk_enforced`
  - [x] `session_guard_enforced`
  - [x] `eod_force_close_enabled`
  - [x] `reconcile_fills_enabled_default`
  - [x] `is_learning_mode`
  - [x] `capital_at_risk`
  - [x] `account_mode_hint`
- [x] Resolver toevoegen: `resolve_mode_capabilities(mode: str) -> ModeCapabilities`.
- [x] Resolver coverage voor modes: `paper`, `sim`, `sim_real_guard`, `real`.

### 1.2 Config normalisatie en matrixvalidatie
- [x] Update `lumina_core/config_loader.py`:
  - [x] mode normalisatie ondersteunt `sim_real_guard`.
  - [x] matrixcheck: `paper -> broker_backend=paper`.
  - [x] matrixcheck: `sim|sim_real_guard|real -> broker_backend=live`.
- [x] Update `lumina_core/engine/engine_config.py`:
  - [x] trade_mode validatie accepteert `sim_real_guard`.
- [x] Update `lumina_core/engine/agent_policy_gateway.py`:
  - [x] valid mode set uitbreiden met `sim_real_guard`.

### 1.3 Fase 1 verificatie
- [x] Unit test toevoegen: `tests/test_mode_capabilities.py`.
- [x] Config/gateway mode tests groen.
- [x] Geen regressie op bestaande mode-tests.

## Fase 2 - Gating en orderpad

- Prioriteit: P0
- ETA: 3 werkdagen

### 2.1 Gatekeeper capability-based maken
- [x] Update `lumina_core/order_gatekeeper.py`:
  - [x] verspreide mode-checks vervangen met capability-resolver.
  - [x] `sim_real_guard` volgt exact `real` voor session/risk gates.
  - [x] `sim` blijft advisory pad behouden.

### 2.2 Operations service mode-semantiek uitbreiden
- [x] Update `lumina_core/engine/operations_service.py`:
  - [x] docstring mode-semantiek aanvullen met `sim_real_guard`.
  - [x] mode-tag toevoegen in relevante audit/log events.
  - [x] submit flow inhoudelijk ongewijzigd buiten gates.

### 2.3 Broker account intent fail-closed maken
- [x] Update `lumina_core/bootstrap.py`:
  - [x] `TRADERLEAGUE_ACCOUNT_MODE=paper|sim|real` afdwingen.
  - [x] `sim` en `sim_real_guard` vereisen `account_mode=sim`.
  - [x] `real` vereist `account_mode=real`.
  - [x] mismatch -> fail-closed startup error.

### 2.4 Fase 2 verificatie
- [x] Uitbreiden `tests/test_order_gatekeeper_contracts.py`.
- [x] Uitbreiden `tests/test_trade_mode_golden_paths.py`.
- [x] Cases bewezen:
  - [x] `sim_real_guard` blockt bij session outside hours.
  - [x] `sim_real_guard` blockt bij risk breach.
  - [x] `sim` advisory gedrag is intact.

## Fase 3 - Runtime parity (EOD + reconciler)

- Prioriteit: P0
- ETA: 2 werkdagen

### 3.1 EOD force-close parity
- [x] Update `lumina_core/runtime_workers.py`:
  - [x] `_enforce_real_eod_force_close(...)` omzetten naar capability-check.
  - [x] actief voor `sim_real_guard` en `real`.
  - [x] uit voor `paper` en `sim`.
  - [x] event codes met mode label toevoegen.

### 3.2 Reconciliation parity
- [x] Update `lumina_core/engine/trade_reconciler.py`:
  - [x] startconditie uitbreiden: `sim_real_guard` + `real`.
  - [x] audit payload uitbreiden met `mode` en `account_mode_hint`.

### 3.3 Fase 3 verificatie
- [x] Uitbreiden `tests/test_runtime_workers.py` met EOD cases.
- [x] Uitbreiden `tests/engine/test_trade_reconciler.py` met `sim_real_guard` cases.
- [x] Bevestigen: reconciler artifacts worden geschreven in `sim_real_guard`.

## Fase 4 - Observability en dashboard

- Prioriteit: P1
- ETA: 2 werkdagen

### 4.1 Metrics toevoegen
- [x] Update `lumina_core/monitoring/observability_service.py`:
  - [x] `lumina_mode_guard_block_total{mode,reason}`.
  - [x] `lumina_mode_eod_force_close_total{mode}`.
  - [x] `lumina_mode_parity_drift_total{baseline="real",candidate="sim_real_guard"}`.

### 4.2 Dashboard parity panel
- [x] Update `lumina_core/engine/dashboard_service.py`:
  - [x] Mode Parity sectie toevoegen.
  - [x] Gate reject ratio tonen.
  - [x] Reconciliation delta tonen.
  - [x] Force-close telling tonen.

### 4.3 Fase 4 verificatie
- [x] Monitoring tests uitbreiden (bestaande monitoring testset).
- [x] Dashboard smoke check uitvoeren.

## Fase 5 - CI safety gate + docs

- Prioriteit: P0
- ETA: 2 werkdagen

### 5.1 CI contractsuite uitbreiden
- [x] Update `.github/workflows/safety-gate.yml`:
  - [x] `sim_real_guard` mode-contract tests toevoegen als blocker.
  - [x] fail hard bij mode-matrix regressie.

### 5.2 Documentatie bijwerken
- [x] Update `lumina_analyse.md` mode-referentie tabel.
- [x] Update `docs/PRODUCTION_RUNBOOK_v51.md` met operator flow voor `sim_real_guard`.
- [x] Update `docs/PRODUCTION_CHECKLIST_v51.md` met parity evidence criteria.
- [x] Launcher/operator docs mode-keuze uitbreiden.

### 5.3 Fase 5 verificatie
- [x] CI pipeline groen inclusief nieuwe mode.
- [x] Runbook/checklist reviewed en bruikbaar voor operators.

## Rollout TODO

### A. Dark launch
- Prioriteit: P0
- ETA: 1 werkdag
- [x] Feature flag toevoegen: `ENABLE_SIM_REAL_GUARD=false` (default).
- [x] Mode technisch aanwezig, niet publiek selecteerbaar.

### B. Staging parallel run
- Prioriteit: P0
- ETA: 5 handelsdagen
- Uitvoer-runbook: `docs/requests/sim_real_guard_rollout_b_staging_runbook.md`
- Automatisering: `scripts/validation/run_sim_real_guard_rollout_b.py`
- Workspace bootstrap: `scripts/validation/bootstrap_sim_real_guard_rollout_b.ps1`
- Release gate rapport: `scripts/validation/build_sim_real_guard_release_gate.py`
- [ ] `sim` en `sim_real_guard` parallel op identieke marktvensters.
- [ ] Parity evidence verzamelen:
  - [ ] gate reasons
  - [ ] reconciliation quality
  - [ ] latency
  - [ ] force-close events

### C. Controlled pilot
- Prioriteit: P1
- ETA: 3 handelsdagen
- Pilot vrijgave gebeurt via `ENABLE_SIM_REAL_GUARD_PILOT=true` op expliciet geselecteerde machines.
- Promotion guard blijft standaard dicht via `ALLOW_SIM_REAL_GUARD_REAL_PROMOTION=false`.
- [ ] Operator-selectie van `sim_real_guard` vrijgeven.
- [ ] Auto-promotion vanuit `sim_real_guard` standaard uit.
- [ ] Extra sign-off verplicht voor promotion-besluiten.

### D. GA
- Prioriteit: P1
- ETA: 1 werkdag
- Publieke launcher-vrijgave gebeurt via `ENABLE_SIM_REAL_GUARD_PUBLIC=true` na green release gate.
- [ ] Mode publiek beschikbaar in launcher/config.
- [ ] Operators getraind op runbook/checklist.

## Acceptatiecriteria (release-go)
- [ ] Geen regressie op `paper|sim|real`.
- [ ] `sim` advisory risk behavior ongewijzigd.
- [ ] `sim_real_guard` en `real` geven equivalent gate-besluit bij gelijke input.
- [ ] EOD force-close actief in `sim_real_guard`.
- [ ] Reconciler/audit evidence aanwezig in `sim_real_guard`.
- [ ] CI contractsuite groen.

## Exit criteria voor live-go/no-go betrouwbaarheid
- [ ] Minimaal 10 opeenvolgende sessies zonder gate/runtime regressie.
- [ ] Reconciliation mismatch-rate binnen SLO.
- [ ] Geen kritieke fail-closed incidenten zonder RCA.
- [ ] Operator sign-off op parity rapport.

## Uitvoer volgorde (aanbevolen)
1. Fase 1 (foundation)
2. Fase 2 (gates + orderpad)
3. Fase 3 (runtime parity)
4. Fase 4 (observability)
5. Fase 5 (CI + docs)
6. Rollout A-D

## Statusoverzicht
- [x] Planning baseline bevestigd (prioriteit + ETA)
- [x] Fase 1 klaar
- [x] Fase 2 klaar
- [x] Fase 3 klaar
- [x] Fase 4 klaar
- [x] Fase 5 klaar
- [x] Rollout A klaar
- [ ] Rollout B klaar
- [ ] Rollout C klaar
- [ ] Rollout D klaar
- [ ] Release-go akkoord

## Delta 2026-04-16 - Risk Transparency Implementation Kickoff

- [x] Centrale audit service toegevoegd: `lumina_core/engine/audit_log_service.py`.
- [x] Gatekeeper audit-integratie toegevoegd voor pre-trade beslissingen inclusief VaR + Monte-Carlo payload.
- [x] Monte-Carlo projected drawdown (regime-aware) toegevoegd in `risk_controller.py` met REAL hard-block pad.
- [x] Reconciler events gespiegeld naar centrale trade-decision auditstream.
- [x] Dashboard hook toegevoegd voor live projected drawdown distribution.
- [x] Config uitgebreid met Monte-Carlo parameters en audit pad.
- [x] Nieuwe tests toegevoegd:
  - [x] `tests/test_audit_log_service.py`
  - [x] `tests/test_trade_reconciler_audit_integration.py`
  - [x] `tests/test_dashboard_drawdown_distribution.py`
  - [x] `tests/test_risk_transparency_e2e.py`

## Delta 2026-04-16 - Step 2 uitgevoerd

- [x] Audit payload verrijkt met expliciete multi-agent herkomst uit blackboard topics (`agent.rl.proposal`, `agent.news.proposal`, `agent.emotional_twin.proposal`, `agent.swarm.proposal`, `agent.tape.proposal`).
- [x] Per agent lineage toegevoegd in audit event (`topic`, `producer`, `correlation_id`, `sequence`, `event_hash`, `prev_hash`, `signal`, `reason`).
- [x] `execution.aggregate` lineage toegevoegd als aparte auditsectie voor end-to-end traceability.
- [x] Tweede e2e test toegevoegd voor dashboardpaneel met runtime snapshot updates:
  - [x] `tests/test_dashboard_drawdown_runtime_e2e.py`

## Delta 2026-04-16 - P0 hardening na kwaliteitsreview

- [x] REAL-mode audit fail-closed afgedwongen in gatekeeper: als `trade_decision` audit write faalt, wordt ordertoelating geblokkeerd.
- [x] Regimehistorie voor Monte-Carlo verdiept met regime-detector brondata (`regime_detector.detect(...)` over historische OHLCV-windowing) naast runtime snapshots/trade history.
- [x] Risk-controller buckets/transities uitgebreid met regime-detector returns en labels voor robuustere regime-aware drawdownprojectie.
- [x] Nieuwe regressietests toegevoegd:
  - [x] `test_enforce_pre_trade_gate_real_fail_closed_when_audit_write_fails`
  - [x] `test_mc_regime_buckets_include_regime_detector_history`
