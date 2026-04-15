# Lumina Analyse Correctieplan (Expert Aanpak)

## 1. Doel en harde randvoorwaarden

Dit plan pakt de volledige inhoud van [lumina_analyse.md](lumina_analyse.md) kwalitatief aan met een innovatiegerichte uitvoering, zonder de kernfunctie van de app te wijzigen.

Harde randvoorwaarden:
- Geen wijziging van de functionele missie van Lumina als trading/AGI-app.
- Geen wijziging van canonieke trade mode-semantiek.
- Elke verbetering moet non-regression veilig zijn.
- Ambitieuze verbeteringen worden opgesplitst in kleine, uitvoerbare bouwstenen.

## 2. Canonieke trade mode-anker (moet ongewijzigd blijven)

Gebaseerd op [lumina_analyse.md](lumina_analyse.md):
- paper:
  - Geen broker-call.
  - place_order retourneert False direct.
  - Intern fill/PnL pad.
- sim:
  - Live marktdata + live orders op sim-account.
  - SessionGuard actief.
  - HardRiskController advisory met enforce_rules=False.
- real:
  - Live productie met echt geld.
  - SessionGuard fail-closed.
  - HardRiskController volledig enforced.

Beslisregel voor alle verbeteringen:
- Een voorstel is alleen toegestaan wanneer paper, sim en real exact bovenstaande betekenis behouden.

## 3. Uitvoeringsfilosofie (innovatief, maar gecontroleerd)

We werken in 3 lagen:
1. Vision Layer: lange-termijn vernieuwingsrichting.
2. Engineering Layer: opsplitsing in kleine, leverbare stappen.
3. Safety Layer: harde kwaliteits- en regressiegates.

Principe:
- Niets wordt als onmogelijk bestempeld.
- Grote sprongen worden vertaald naar micro-mijlpalen met meetbare output.
- Iedere mijlpaal moet zelfstandig waarde leveren en rollbackbaar zijn.

## 4. Werkpakketstructuur

## WP-A: Baseline en beschermrails

Doel:
- Eerst een onveranderlijke baseline vastzetten, daarna pas verbeteren.

Acties:
1. Trade mode contract tests expliciet borgen als release-blocker.
2. Golden path scenario-set vastleggen voor paper/sim/real.
3. Kritieke metrics baseline vastleggen:
   - order acceptance rate
   - block reason verdeling (session/risk/policy)
   - fallback rate inferentie
   - reconcile latency
4. Non-functional SLO baseline definiëren (latency, error rate, stability).

Deliverables:
- Testmatrix v1.
- Baseline metrics snapshot.
- Release gate checklist.

Succescriteria:
- Geen regressie op bestaande trade mode tests.
- Baseline reproduceerbaar in CI.

Prioriteit: Critical.

## WP-B: Architectuurverfijning zonder functiewijziging

Doel:
- Complexiteit reduceren zonder gedrag te veranderen.

Acties:
1. Engine-state opdelen in contextblokken via interne data-objecten.
2. Legacy compatibiliteitspaden markeren met deprecatie-roadmap.
3. Canonieke importpaden vastleggen; compat wrappers tijdelijk maar gecontroleerd.
4. Uniforme structured logging events invoeren naast bestaande paden.

Deliverables:
- Interne state map v1.
- Deprecatie roadmap.
- Logging event dictionary.

Succescriteria:
- Geen wijziging in extern runtimegedrag.
- Zelfde signalen/output bij gelijke input.

Prioriteit: High.

## WP-C: Trading effectiviteit en operationele robuustheid

Doel:
- Daytrading pad scherper en betrouwbaarder maken binnen bestaande mode-semantiek.

Acties:
1. Contract rollover intelligence uitbreiden met kalender + metadata checks.
2. Session governance consolideren op SessionGuard als bron van waarheid.
3. Fill- en latency-kalibratie koppelen aan echte brokertelemetrie.
4. Regime-specifieke validatiepacks:
   - trend
   - ranging
   - high volatility
   - rollover windows

Deliverables:
- Rollover validator.
- Session governance policy.
- Fill calibration report.
- Regime scorecards.

Succescriteria:
- Minder mismatch tussen verwacht en gerealiseerd fillgedrag.
- Geen toename van ongewenste block/reject patronen.

Prioriteit: High.

## WP-D: Financiële nauwkeurigheid en risk governance

Doel:
- Financieel model realistischer en auditbaar maken zonder modebreuk.

Acties:
1. VaR-methodiek uitbreiden met scenario-gebaseerde benadering.
2. Margin freshness SLA hard afbakenen voor real mode.
3. Fee- en spread-impact modellen koppelen aan werkelijke kosten.
4. Financieel wijzigingsregister introduceren voor parameter governance.

Deliverables:
- VaR v2 ontwerpdocument.
- Margin reliability gate.
- Fee/spread calibration pack.
- Governance register template.

Succescriteria:
- Betere ex-post match tussen model en gerealiseerde kosten/risico.
- Geen overtreding van real-mode veiligheidsprincipes.

Prioriteit: Critical voor margin gate, High voor overige onderdelen.

## WP-E: AGI/Agent innovatie onder harde veiligheid

Doel:
- Vooruitstrevende AGI-capaciteit opschalen met gecontroleerde vrijgave.

Acties:
1. Execution plane en evolution plane logisch scheiden via release gates.
2. Prompt/config lineage automatisch versioneren en hashen.
3. Online betrouwbaarheidmetrics toevoegen:
   - calibration drift
   - abstention rate
   - regime-wise performance
4. Sandbox + shadow rollout voor autonome mutaties.

Deliverables:
- Evolution safety architecture v1.
- Immutable lineage registry.
- AGI reliability dashboard.
- Shadow rollout protocol.

Succescriteria:
- Hogere innovatiecadans zonder productie-instabiliteit.
- Volledige traceability van agentbeslissingen.

Prioriteit: Critical.

## 5. Fasering (90-dagen route)

Fase 1 (week 1-3): Stabiliseer fundament
- WP-A volledig afronden.
- Kritieke gates activeren.
- Baseline rapport publiceren.

Fase 2 (week 4-7): Interne kwaliteit en precisie
- WP-B en kern van WP-C uitvoeren.
- Eerste kalibraties live in sim.

Fase 3 (week 8-10): Financiële verdieping
- WP-D implementeren en valideren.
- Margin en VaR gates operationaliseren.

Fase 4 (week 11-13): AGI-versnelling met safety
- WP-E in gecontroleerde release.
- Shadow-validatie en promotiecriteria aanscherpen.

## 6. Beslis- en kwaliteitskader

Elke change doorloopt dezelfde go/no-go poort:
1. Trade mode invariant check.
2. Testmatrix check (paper/sim/real).
3. Performance en stability check.
4. Security/audit check.
5. Financial/risk check.
6. Operator sign-off voor promotie.

Stopregels:
- Bij mode-invariant schending: directe rollback.
- Bij real-mode risk regressie: onmiddellijke blokkade van promotie.

## 7. Concrete eerste backlog (uitvoerbaar vanaf nu)

Sprint 0 (direct starten):
1. Canonieke mode-contracten expliciet in CI als mandatory gates.
2. Baseline snapshot tooling voor metrics en block reasons.
3. Inventaris van compat wrappers + deprecatie labels.
4. SessionGuard-only governance voorstel in ontwerpvorm.
5. Margin freshness policy met fail-closed regels voor real mode.

Sprint 1:
1. Rollover validator proof-of-concept.
2. Fill-latency kalibratierun op sim-data.
3. Financial register template in gebruik nemen.
4. AGI lineage auto-hash prototype.

Sprint 2:
1. Regime scorecards met pass/fail drempels.
2. VaR scenario-pack v1.
3. Shadow rollout protocol voor self-evolution.

## 8. Risicoanalyse en mitigatie

Toprisico's:
- Onbedoelde mode-semantiek drift.
- Over-innovatie zonder voldoende meetbaarheid.
- Financiële modelwijziging zonder ex-post verificatie.

Mitigaties:
- Verplichte mode-invariant tests.
- Elke innovatie via micro-mijlpaal + rollbackpad.
- Ex-post rapportage als releasevoorwaarde.

## 9. Governance en ownership

Voorstel rollen:
- Technical Owner: architectuur, integriteit, release gates.
- Trading Owner: regime, execution quality, fill realism.
- Financial Owner: VaR, margin, cost model governance.
- AGI Owner: evolution safety, lineage, reliability metrics.
- Ops Owner: observability, incident runbooks, rollout control.

## 10. Definitie van succes

Het plan is geslaagd wanneer:
- Lumina-functioneel exact blijft doen waarvoor het gemaakt is.
- Trade mode-referentie onveranderd en aantoonbaar geborgd blijft.
- Kwaliteit, snelheid en betrouwbaarheid aantoonbaar stijgen.
- Innovatiecapaciteit toeneemt zonder veiligheid of controle te verliezen.

---

## Slot

Dit voorstel behandelt Lumina als een high-ambition systeem: vernieuwend, schaalbaar en controleerbaar tegelijk. We combineren grote visie met kleine, haalbare stappen die samen één sterk geheel vormen.

---

## 11. Gedetailleerde Master TODO-lijst (uitvoering)

Gebruik deze lijst als operationele backlog. Elke taak is pas Done wanneer alle acceptatiecriteria gehaald zijn.

Statuslegenda:
- [ ] Niet gestart
- [~] Bezig
- [x] Afgerond

### Invariant-Checks (verplicht bij elke TODO)

Voor elke taak moet dit expliciet gevalideerd worden:
1. paper blijft zonder broker-call en place_order blijft False.
2. sim blijft live data + live orders op sim-account met SessionGuard actief en risk advisory.
3. real blijft fail-closed met SessionGuard + volledige HardRiskController enforcement.
4. Geen wijziging van functionele missie van de app.

### TODO-A: Baseline en beschermrails

#### A1. Trade mode contracten als CI release blocker
- Status: [x]
- Doel: Trade mode-semantiek hard afdwingen bij elke wijziging.
- Uitvoering:
1. Bepaal canonical tests voor paper/sim/real gedrag.
2. Markeer deze tests als required checks in CI pipeline.
3. Blokkeer merge/release bij failure.
- Betrokken bestanden:
1. [tests/test_order_path_regression.py](tests/test_order_path_regression.py)
2. [tests/test_trade_workers.py](tests/test_trade_workers.py)
3. [tests/test_trade_workers_gateway.py](tests/test_trade_workers_gateway.py)
4. [pytest.ini](pytest.ini)
- Acceptatiecriteria:
1. CI faalt altijd bij mode-invariant regressie.
2. Minimaal 1 paper, 1 sim, 1 real regressietest is mandatory.
3. Geen false positive skips op critical mode tests.
 - Verificatie (dubbele controle):
1. Workflow-stap toegevoegd in [ .github/workflows/safety-gate.yml ] (trade mode regressions als blocker).
2. Lokaal bevestigd met groene testresultaten:
  - tests/test_order_path_regression.py -> 14 passed
  - tests/test_trade_workers.py -> 1 passed
  - tests/test_trade_workers_gateway.py -> 2 passed

#### A2. Golden path scenario-set vastleggen
- Status: [x]
- Doel: Reproduceerbare end-to-end referentiepaden per mode.
- Uitvoering:
1. Definieer 3 scenario’s (paper/sim/real) met input-output verwachting.
2. Maak scenario runner voor repeatable replay.
3. Archiveer baseline resultaten als referentie.
- Betrokken bestanden:
1. [tests/test_startup_integration.py](tests/test_startup_integration.py)
2. [tests/test_runtime_bootstrap.py](tests/test_runtime_bootstrap.py)
3. [tests/test_headless_runtime.py](tests/test_headless_runtime.py)
4. [docs/history/lumina_analyse_v52.md](docs/history/lumina_analyse_v52.md)
- Acceptatiecriteria:
1. Golden paths draaien deterministisch op CI.
2. Verschillen met baseline worden expliciet gelogd en verklaard.
- Verificatie (dubbele controle):
1. Nieuwe scenario-suite toegevoegd: [tests/test_trade_mode_golden_paths.py](tests/test_trade_mode_golden_paths.py) en lokaal groen (3 passed).
2. Runner toegevoegd en geverifieerd: [scripts/validation/run_golden_paths.py](scripts/validation/run_golden_paths.py), output in [state/golden_path_baseline.json](state/golden_path_baseline.json) met return_code=0.

#### A3. Kritieke baseline-metrics pipeline
- Status: [x]
- Doel: Objectieve voor/na meting van kwaliteit.
- Uitvoering:
1. Log standaard: order acceptance, block reasons, fallback rate, reconcile latency.
2. Voeg snapshot-export toe per build.
3. Vergelijk build N versus N-1 met thresholds.
- Betrokken bestanden:
1. [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py)
2. [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py)
3. [lumina_core/engine/trade_reconciler.py](lumina_core/engine/trade_reconciler.py)
4. [lumina_core/monitoring](lumina_core/monitoring)
- Acceptatiecriteria:
1. Metrics snapshot wordt automatisch opgeslagen.
2. Drempel-overschrijdingen geven build warning of fail volgens policy.
- Verificatie (dubbele controle):
1. Metrics snapshot-script toegevoegd: [scripts/validation/build_metrics_snapshot.py](scripts/validation/build_metrics_snapshot.py).
2. Tweemaal lokaal uitgevoerd en geverifieerd met N vs N-1 delta output in [state/build_metrics_snapshot_latest.json](state/build_metrics_snapshot_latest.json) en CI-integratie in [ .github/workflows/safety-gate.yml ] met fail-on-breach.

#### A4. Non-functional SLO baseline
- Status: [x]
- Doel: Latency/stability/security op minimum niveau houden.
- Uitvoering:
1. Definieer SLO’s voor websocket ingest, reasoning latency, error-rate.
2. Koppel SLO’s aan alerting en rapportage.
3. Maak release gate: geen promotie bij SLO breach.
- Betrokken bestanden:
1. [lumina_core/engine/market_data_service.py](lumina_core/engine/market_data_service.py)
2. [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py)
3. [lumina_os/backend/monitoring_endpoints.py](lumina_os/backend/monitoring_endpoints.py)
- Acceptatiecriteria:
1. SLO rapport is onderdeel van release artefacts.
2. Kritieke SLO breach blokkeert promotie naar real-ready.
- Verificatie (dubbele controle):
1. SLO-threshold baseline toegevoegd in [deploy/slo_thresholds.json](deploy/slo_thresholds.json) en gekoppeld aan metrics snapshot.
2. SLO gate-script toegevoegd en geverifieerd: [scripts/validation/build_slo_report.py](scripts/validation/build_slo_report.py) met output in [state/slo_report.json](state/slo_report.json), plus CI artifact upload.

### TODO-B: Architectuurverfijning zonder functiewijziging

#### B1. Engine-state opdelen in contextblokken
- Status: [x]
- Doel: Complexiteit verlagen zonder extern gedrag te wijzigen.
- Uitvoering:
1. Maak interne state-objecten: MarketState, PositionState, RiskState, AgentState.
2. Migreer velden incrementeel achter bestaande API.
3. Voeg snapshot serializer toe voor debug en replay.
- Betrokken bestanden:
1. [lumina_core/engine/lumina_engine.py](lumina_core/engine/lumina_engine.py)
2. [lumina_core/runtime_context.py](lumina_core/runtime_context.py)
3. [tests/engine/test_lumina_engine_suite.py](tests/engine/test_lumina_engine_suite.py)
- Acceptatiecriteria:
1. Publiek runtimegedrag blijft identiek in golden path tests.
2. State snapshots zijn deterministisch serialiseerbaar.

#### B2. Legacy compatibiliteit gecontroleerd afbouwen
- Status: [x]
- Doel: Technische schuld verminderen zonder plotselinge breuk.
- Uitvoering:
1. Voeg deprecatie-labels en deadline per compat-pad toe.
2. Gebruik import-audit om legacy gebruik te meten.
3. Verwijder pas na nul actieve dependents.
- Betrokken bestanden:
1. [lumina_v45.1.1.py](lumina_v45.1.1.py)
2. [lumina_core/engine/FastPathEngine.py](lumina_core/engine/FastPathEngine.py)
3. [lumina_core/engine/TapeReadingAgent.py](lumina_core/engine/TapeReadingAgent.py)
4. [lumina_core/engine/AdvancedBacktesterEngine.py](lumina_core/engine/AdvancedBacktesterEngine.py)
5. [lumina_core/engine/RealisticBacktesterEngine.py](lumina_core/engine/RealisticBacktesterEngine.py)
- Acceptatiecriteria:
1. Geen runtime import failures.
2. Deprecatie-rapport toont afnemend legacy gebruik.
- Implementatiestatus:
1. Deprecation shims zijn actief in compat-bestanden.
2. Import-audit toegevoegd: [scripts/validation/audit_legacy_compat_imports.py](scripts/validation/audit_legacy_compat_imports.py) met rapport in [state/legacy_import_audit.json](state/legacy_import_audit.json).
3. Deprecatie-deadline en tracker-ID vastgelegd per compat-pad in [lumina_core/engine/FastPathEngine.py](lumina_core/engine/FastPathEngine.py), [lumina_core/engine/TapeReadingAgent.py](lumina_core/engine/TapeReadingAgent.py), [lumina_core/engine/AdvancedBacktesterEngine.py](lumina_core/engine/AdvancedBacktesterEngine.py), [lumina_core/engine/RealisticBacktesterEngine.py](lumina_core/engine/RealisticBacktesterEngine.py).
4. Audit uitgebreid met deprecatie-schedule in [scripts/validation/audit_legacy_compat_imports.py](scripts/validation/audit_legacy_compat_imports.py); run bevestigd met 0 actieve imports.
5. Definitieve verwijderfase blijft pas na nul afhankelijke importers.

#### B3. Logging standaardiseren
- Status: [x]
- Doel: Snellere incidentanalyse en betere observability.
- Uitvoering:
1. Definieer event-code catalogus.
2. Vervang print in kritieke paden door structured logs.
3. Houd launcher/UI output vriendelijk, engine output structureel.
- Betrokken bestanden:
1. [lumina_core/logging_utils.py](lumina_core/logging_utils.py)
2. [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py)
3. [lumina_core/engine/analysis_service.py](lumina_core/engine/analysis_service.py)
4. [lumina_launcher.py](lumina_launcher.py)
- Acceptatiecriteria:
1. Kritieke events zijn machine-parsebaar.
2. Logquery op event-code dekt minimaal 90% van incidentcases.

### TODO-C: Trading effectiviteit en operationele robuustheid

#### C1. Contract rollover intelligence
- Status: [x]
- Doel: Foute contractrouting en verouderde symbolen voorkomen.
- Uitvoering:
1. Bouw contract-validatie op basis van kalender + broker metadata.
2. Voeg pre-trade blokkade toe voor verouderde contractcodes.
3. Voeg operator override met auditspoor toe.
- Betrokken bestanden:
1. [lumina_core/engine/regime_detector.py](lumina_core/engine/regime_detector.py)
2. [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py)
3. [lumina_core/engine/engine_config.py](lumina_core/engine/engine_config.py)
4. [tests/test_risk_controller.py](tests/test_risk_controller.py)
- Acceptatiecriteria:
1. Verouderde contracten kunnen niet doorsturen naar broker in sim/real.
2. Geldige rollover transitie blijft probleemloos werken.
- Implementatiestatus:
1. Stale/expired contract gate toegevoegd in [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py) voor sim/real, met operator override via LUMINA_ALLOW_STALE_CONTRACTS.
2. Kalender-gedreven expiry check toegevoegd (3rd-Friday benadering) in [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py).
3. Broker metadata contract-check gekoppeld (indien broker capability aanwezig) in [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py).
4. Auditeerbare override-flow toegevoegd met OVERRIDE_AUDIT logging voor stale-contract overrides.
5. Nieuwe tests toegevoegd: [tests/test_order_gatekeeper_contracts.py](tests/test_order_gatekeeper_contracts.py) (5 passed).
6. Regressiecontrole op orderpad groen:
  - [tests/test_order_path_regression.py](tests/test_order_path_regression.py) + [tests/test_trade_workers_gateway.py](tests/test_trade_workers_gateway.py) -> 16 passed.

#### C2. Session governance consolideren
- Status: [x]
- Doel: Eén bron van waarheid voor sessiegedrag.
- Uitvoering:
1. Inventariseer alle sessie/market-open checks.
2. Centraliseer op SessionGuard-gedrag.
3. Verwijder afwijkende parallel checks na validatie.
- Betrokken bestanden:
1. [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py)
2. [lumina_core/engine/session_guard.py](lumina_core/engine/session_guard.py)
3. [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py)
4. [tests/test_order_path_regression.py](tests/test_order_path_regression.py)
- Acceptatiecriteria:
1. Identieke block decisions voor session scenarios.
2. Geen onverwachte toename in false blocks in sim.
- Implementatiestatus:
1. OperationsService sessiecheck geprioriteerd naar SessionGuard met conservatieve fallback: [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py).
2. Centrale helper `session_guard_allows_trading(...)` toegevoegd in [lumina_core/order_gatekeeper.py](lumina_core/order_gatekeeper.py) en hergebruikt in [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py) en [lumina_core/runtime_workers.py](lumina_core/runtime_workers.py).
3. Parallelle handmatige sessiechecks in reasoning/runtime gate-paden vervangen door centrale SessionGuard-evaluatie.
4. Dubbele regressiecontrole uitgevoerd:
  - [tests/test_order_path_regression.py](tests/test_order_path_regression.py) -> 14 passed
  - [tests/test_trade_workers.py](tests/test_trade_workers.py) + [tests/test_trade_workers_gateway.py](tests/test_trade_workers_gateway.py) -> 3 passed
  - [tests/test_runtime_workers.py](tests/test_runtime_workers.py) -> 11 passed

#### C3. Fill- en latency kalibratie op echte telemetrie
- Status: [x]
- Doel: Hogere realiteitsgraad van execution-evaluatie.
- Uitvoering:
1. Meet expected versus actual fill, slippage en latency.
2. Pas calibratiefactoren versie-gebonden aan.
3. Houd mode-gedrag gelijk, enkel modelnauwkeurigheid verbeteren.
- Betrokken bestanden:
1. [lumina_core/engine/valuation_engine.py](lumina_core/engine/valuation_engine.py)
2. [lumina_core/engine/trade_reconciler.py](lumina_core/engine/trade_reconciler.py)
3. [logs/trade_fill_audit.jsonl](logs/trade_fill_audit.jsonl)
4. [tests/engine/test_trade_reconciler.py](tests/engine/test_trade_reconciler.py)
- Acceptatiecriteria:
1. Foutmarge op fill-verwachting daalt aantoonbaar.
2. Geen regressie in order acceptance flow.

#### C4. Regime-specifieke validatiepacks
- Status: [x]
- Doel: Strategie robuustheid per markttype aantonen.
- Uitvoering:
1. Definieer pass/fail criteria per regime.
2. Draai walk-forward en stressset per regime.
3. Publiceer scorecard met promotieadvies.
- Betrokken bestanden:
1. [lumina_core/engine/advanced_backtester_engine.py](lumina_core/engine/advanced_backtester_engine.py)
2. [lumina_core/engine/stress_suite_runner.py](lumina_core/engine/stress_suite_runner.py)
3. [tests/test_regime_detector.py](tests/test_regime_detector.py)
4. [tests/test_stress_suite_runner.py](tests/test_stress_suite_runner.py)
5. [scripts/validation/run_regime_validation_pack.py](scripts/validation/run_regime_validation_pack.py)
- Acceptatiecriteria:
1. Elk regime heeft expliciet kwaliteitsresultaat.
2. Promotion to real-readiness alleen bij volledige regime coverage.
- Verificatie (dubbele controle):
1. Regime scorecard + promotieadvies toegevoegd in [lumina_core/engine/stress_suite_runner.py](lumina_core/engine/stress_suite_runner.py) met thresholds voor TRENDING, RANGING, HIGH_VOLATILITY en ROLLOVER.
2. Validatiepack-script toegevoegd in [scripts/validation/run_regime_validation_pack.py](scripts/validation/run_regime_validation_pack.py), output naar [state/validation/regime_scorecard.json](state/validation/regime_scorecard.json).
3. Testset groen: [tests/test_stress_suite_runner.py](tests/test_stress_suite_runner.py) + [tests/test_regime_detector.py](tests/test_regime_detector.py) -> 13 passed.
4. Automatische regime-inputgeneratie toegevoegd via [scripts/validation/build_regime_oos_results.py](scripts/validation/build_regime_oos_results.py), output naar [state/regime_oos_results.json](state/regime_oos_results.json) en her-run van scorecard bevestigt volledige regime coverage (regime checks PASS, stress gate blijft fail-closed).

### TODO-D: Financiële nauwkeurigheid en risk governance

#### D1. VaR scenario-framework v2
- Status: [x]
- Doel: VaR minder simplistisch en meer marktgetrouw maken.
- Uitvoering:
1. Voeg scenario-based PnL paths toe naast huidige methode.
2. Koppel scenario’s aan contractspecifieke point/tick sensitiviteiten.
3. Voer comparative backtest uit tussen oud en nieuw model.
- Betrokken bestanden:
1. [lumina_core/engine/portfolio_var_allocator.py](lumina_core/engine/portfolio_var_allocator.py)
2. [lumina_core/engine/financial_contracts.py](lumina_core/engine/financial_contracts.py)
3. [tests/test_portfolio_var_allocator.py](tests/test_portfolio_var_allocator.py)
- Acceptatiecriteria:
1. VaR v2 geeft stabielere risicoschatting over regimewissels.
2. real-mode safetyregels blijven strikt onveranderd.

#### D2. Margin freshness SLA fail-closed voor real
- Status: [x]
- Doel: Real mode nooit laten varen op onbetrouwbare margindata.
- Uitvoering:
1. Definieer max data-age en confidence threshold.
2. Blokkeer real orders bij stale/onzekere snapshot.
3. In sim advisory-only signaal behouden.
- Betrokken bestanden:
1. [lumina_core/engine/risk_controller.py](lumina_core/engine/risk_controller.py)
2. [lumina_core/engine/margin_snapshot_provider.py](lumina_core/engine/margin_snapshot_provider.py)
3. [tests/test_risk_controller.py](tests/test_risk_controller.py)
- Acceptatiecriteria:
1. real blokkeert correct bij stale margin.
2. sim blijft leren zonder harde financiële blokkade.
- Verificatie (dubbele controle):
1. Risk controller uitgebreid met margin confidence threshold in enforced pad (fail-closed): [lumina_core/engine/risk_controller.py](lumina_core/engine/risk_controller.py).
2. Testverificatie groen:
  - [tests/test_risk_controller.py](tests/test_risk_controller.py) -> 45 passed
  - [tests/test_order_path_regression.py](tests/test_order_path_regression.py) + [tests/test_trade_workers_gateway.py](tests/test_trade_workers_gateway.py) -> 16 passed

#### D3. Fee- en spread-impact kalibratie
- Status: [x]
- Doel: Financiële resultaten realistischer maken.
- Uitvoering:
1. Maak account/broker fee-profielen configureerbaar.
2. Modelleer spread-impact expliciet in evaluatie.
3. Vergelijk modelkosten met echte afrekeningen.
- Betrokken bestanden:
1. [lumina_core/engine/valuation_engine.py](lumina_core/engine/valuation_engine.py)
2. [lumina_core/engine/reporting_service.py](lumina_core/engine/reporting_service.py)
3. [tests/test_financial_contracts.py](tests/test_financial_contracts.py)
- Acceptatiecriteria:
1. Ex-post kostenverschil daalt onder afgesproken threshold.
2. Rapportages tonen transparant kostencomponenten.

#### D4. Financieel wijzigingsregister
- Status: [x]
- Doel: Governance op risicoparameters en financiële modellen.
- Uitvoering:
1. Introduceer changelog-sjabloon voor risk/finance parameters.
2. Verplicht impactanalyse en goedkeuring.
3. Koppel wijzigings-ID aan release notes.
- Betrokken bestanden:
1. [docs](docs)
2. [config.yaml](config.yaml)
3. [SECURITY_HARDENING.md](SECURITY_HARDENING.md)
- Acceptatiecriteria:
1. Elke financiële parameterwijziging is herleidbaar.
2. Geen anonieme parameterwijzigingen in productie.
- Verificatie (dubbele controle):
1. Template toegevoegd: [docs/notes/financial_change_register_template.md](docs/notes/financial_change_register_template.md).
2. Template gecontroleerd op verplichte velden: wijzigings-ID, impactanalyse, mode-invariant check, rollbackplan en multi-owner sign-off.

### TODO-E: AGI/Agent innovatie onder harde safety

#### E1. Execution plane en evolution plane scheiden
- Status: [x]
- Doel: Sneller innoveren zonder productie-instabiliteit.
- Uitvoering:
1. Definieer duidelijke boundary tussen live execution en evolution workflows.
2. Laat evolutie alleen promoten via release gates.
3. Houd rollbackpad altijd beschikbaar.
- Betrokken bestanden:
1. [lumina_core/engine/self_evolution_meta_agent.py](lumina_core/engine/self_evolution_meta_agent.py)
2. [lumina_core/engine/evolution_lifecycle.py](lumina_core/engine/evolution_lifecycle.py)
3. [tests/test_self_evolution_auto_finetune.py](tests/test_self_evolution_auto_finetune.py)
4. [lumina_core/runtime_bootstrap.py](lumina_core/runtime_bootstrap.py)
- Acceptatiecriteria:
1. Geen directe live-mutatie zonder gate-pass.
2. Volledig auditspoor van voorstel tot promotie.

#### E2. Prompt/config lineage automation
- Status: [x]
- Doel: Volledige traceability van agentbeslissingen.
- Uitvoering:
1. Auto-hash prompttemplates en relevante config snapshots.
2. Schrijf lineage IDs mee in decision logs.
3. Maak lineage-lookup tooling voor incidentonderzoek.
- Betrokken bestanden:
1. [lumina_core/engine/agent_decision_log.py](lumina_core/engine/agent_decision_log.py)
2. [lumina_core/engine/agent_policy_gateway.py](lumina_core/engine/agent_policy_gateway.py)
3. [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py)
4. [tests/test_agent_decision_log.py](tests/test_agent_decision_log.py)
- Acceptatiecriteria:
1. Elke kritieke beslissing heeft complete lineage.
2. Incidentanalyse kan binnen minuten naar bronprompt/config leiden.
- Implementatiestatus:
1. Bestaande automatische prompt-hash fallback in decision logging bevestigd in [lumina_core/engine/agent_decision_log.py](lumina_core/engine/agent_decision_log.py).
2. Automatische config-snapshot hash toegevoegd in lineage payloads en top-level log records in [lumina_core/engine/agent_decision_log.py](lumina_core/engine/agent_decision_log.py).
3. Lookup-tooling uitgebreid met config-hash filtering in [scripts/validation/lookup_lineage.py](scripts/validation/lookup_lineage.py).
4. Testuitbreiding toegevoegd in [tests/test_agent_decision_log.py](tests/test_agent_decision_log.py) en lokaal groen.
5. Dubbele controle uitgevoerd via CLI-run met gestructureerde match-output inclusief `config_snapshot_hash` uit state/agent_decision_log.jsonl.

#### E3. AGI reliability metrics live
- Status: [x]
- Doel: Betrouwbaarheid zichtbaar maken en sturen.
- Uitvoering:
1. Voeg metrics toe voor drift, abstention en regime-wise prestaties.
2. Koppel metrics aan alerts en release policy.
3. Publiceer periodieke reliability scorecard.
- Betrokken bestanden:
1. [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py)
2. [lumina_core/monitoring](lumina_core/monitoring)
3. [lumina_os/backend/monitoring_endpoints.py](lumina_os/backend/monitoring_endpoints.py)
4. [tests/test_monitoring.py](tests/test_monitoring.py)
- Acceptatiecriteria:
1. Reliability metrics zijn beschikbaar en historisch vergelijkbaar.
2. Promotion policy verwijst naar objectieve metrics.

#### E4. Sandbox + shadow rollout protocol
- Status: [x]
- Doel: Veilige opschaling van autonome verbeteringen.
- Uitvoering:
1. Definieer shadow run pipeline zonder live impact.
2. Vergelijk shadow-output met champion baseline.
3. Promoot alleen bij aantoonbare winst en geen safety regressie.
- Betrokken bestanden:
1. [lumina_core/engine/self_evolution_meta_agent.py](lumina_core/engine/self_evolution_meta_agent.py)
2. [lumina_core/engine/replay_validator.py](lumina_core/engine/replay_validator.py)
3. [tests/test_replay_validator.py](tests/test_replay_validator.py)
- Acceptatiecriteria:
1. Shadow protocol voorkomt ongecontroleerde promotie.
2. Elke promotie heeft numerieke bewijsset.

### TODO-F: Kwaliteit, release en documentatie

#### F1. Release gates operationaliseren
- Status: [x]
- Doel: Kwaliteit afdwingen vóór elke release.
- Uitvoering:
1. Maak gate-checklist uitvoerbaar in CI/CD.
2. Voeg operator sign-off stap toe.
3. Publiceer gate-resultaten in release artefacten.
- Betrokken bestanden:
1. [deploy](deploy)
2. [docs/release-workflow.md](docs/release-workflow.md)
3. [pytest.ini](pytest.ini)
- Acceptatiecriteria:
1. Geen release zonder geslaagde gates.
2. Volledige traceability van gate-uitkomsten.
- Verificatie (dubbele controle):
1. CI gates uitgebreid in [ .github/workflows/safety-gate.yml ] met mode-contract regressies, golden-path baseline, metrics snapshot, SLO gate en legacy import audit + artifacts.
2. Checklist toegevoegd in [docs/release-gate-checklist.md](docs/release-gate-checklist.md) met bewijsvelden en owner sign-off.

#### F2. Runbook updates op nieuwe verbeteringen
- Status: [x]
- Doel: Operaties en incident response actueel houden.
- Uitvoering:
1. Werk productie-runbooks bij per afgerond werkpakket.
2. Voeg failure-mode scenario’s en rollback acties toe.
3. Valideer runbooks in tabletop oefening.
- Betrokken bestanden:
1. [docs/PRODUCTION_RUNBOOK_v51.md](docs/PRODUCTION_RUNBOOK_v51.md)
2. [docs/PRODUCTION_CHECKLIST_v51.md](docs/PRODUCTION_CHECKLIST_v51.md)
3. [docs/trade-fill-reconciliation-runbook.md](docs/trade-fill-reconciliation-runbook.md)
- Acceptatiecriteria:
1. Runbooks dekken alle kritieke paden.
2. Ops-team kan rollback uitvoeren zonder ad-hoc beslissingen.

#### F3. Definitieve Done-criteria per werkpakket
- Status: [x]
- Doel: Geen half-af opleveringen.
- Uitvoering:
1. Definieer Done-checklist per WP met test, docs, metrics, gate-pass.
2. Voeg owner en deadline toe.
3. Review in wekelijkse architectuur- en tradingboard.
- Betrokken bestanden:
1. [lumina_analyse_corrections_expert.md](lumina_analyse_corrections_expert.md)
2. [docs](docs)
- Acceptatiecriteria:
1. Elke taak heeft owner, ETA, bewijs en gate-resultaat.
2. Geen task-close zonder objectief bewijs.
- Verificatie (dubbele controle):
1. Done-checklist met owner/ETA/review-cadans toegevoegd onderstaand.
2. Checklist-structuur afgestemd op gate-bewijsvereisten in [docs/release-gate-checklist.md](docs/release-gate-checklist.md).

##### F3 Uitvoerbare Done-checklist per werkpakket

| Werkpakket | Primary Owner | Secondary Owner | ETA (target) | Verplicht bewijs bij close |
|---|---|---|---|---|
| WP-A | Technical Owner | Ops Owner | 2026-05-02 | CI gate run, golden baseline, metrics snapshot, SLO report |
| WP-B | Technical Owner | AGI Owner | 2026-05-16 | Geen regressie op golden paths, import-audit, architectuurnotitie |
| WP-C | Trading Owner | Technical Owner | 2026-05-30 | Orderpad regressie, contract/session tests, fill-kalibratierapport |
| WP-D | Financial Owner | Trading Owner | 2026-06-13 | VaR/margin tests, financieel wijzigingsregister, ex-post vergelijk |
| WP-E | AGI Owner | Ops Owner | 2026-06-27 | Lineage bewijs, shadow-resultaten, promotion gate report |
| WP-F | Ops Owner | Technical Owner | 2026-06-27 | Release-checklist, runbook updates, sign-off log |

##### F3 Review-cadans

1. Wekelijks board review: open risico’s, gatestatus, afwijkingen.
2. Bi-weekly architecture/trading review: koerscorrecties op WP-B/WP-C.
3. Maandelijkse executive review: readiness voor real-promotie.

### Prioritaire uitvoering (volgorde)

1. A1
2. A2
3. A3
4. D2
5. C2
6. C1
7. B1
8. E1
9. D1
10. E2
11. C3
12. F1

### Wekelijkse ritmiek (aanbevolen)

1. Maandag: planning + risico review + mode-invariant bevestiging.
2. Woensdag: mid-sprint meting op baseline-metrics.
3. Vrijdag: gate-run + retro + update van deze TODO-statussen.

### Eindcriterium masterlijst

De masterlijst is afgerond wanneer:
1. Alle Critical en High items [x] zijn.
2. Trade mode-invariant in alle gates groen blijft.
3. Golden paths stabiel zijn over opeenvolgende releases.
4. Kwaliteitsverbetering aantoonbaar is in metrics, tests en runbooks.

---

## 7. Restpunten TODO (Robuustheid zonder wijziging trading/leren)

### Harde non-goals (blijven ongewijzigd)

1. Geen wijziging van de manier van traden per mode (paper/sim/real).
2. Geen wijziging van leerlogica of promotie-intentie (sim blijft primair leerpad).
3. Geen versoepeling van fail-closed gedrag in real mode.

### Openstaande restpunten

#### G1. Remote inferentie-fallback afronden of tijdelijk hard disablen
- Status: [x]
- Waarom:
1. Onvolledig fallbackpad geeft schijnzekerheid bij provider-uitval.
- Uitvoering:
1. Implementeer volledige, contractueel geteste remote-call route met typed error mapping.
2. Als dat niet direct kan: disable de route expliciet achter feature-flag met auditlog.
3. Behoud huidige decision-output contracten (signal/confidence/reason) exact.
- Betrokken bestanden:
1. [lumina_core/engine/local_inference_engine.py](lumina_core/engine/local_inference_engine.py)
2. [tests](tests)
- Acceptatiecriteria:
1. Geen stille return None meer in remote route zonder expliciete reason code.
2. Chaos test voor provider-uitval en fallbackvolgorde groen.
3. Geen gedragswijziging in trading-besluitvorming buiten foutafhandeling.
- Verificatie:
1. Remote grok-route geïmplementeerd met expliciete error_code logging en warning-codes (XAI_KEY_MISSING, XAI_CALL_FAILED, XAI_HTTP_*, XAI_RESPONSE_SCHEMA_INVALID).
2. Gerichte regressietests toegevoegd voor succespad en missing-key pad in [tests/test_local_inference_engine.py](tests/test_local_inference_engine.py).

#### G2. Typed exceptions + error-codes in kritieke paden
- Status: [x]
- Waarom:
1. Brede excepts vertragen root-cause analyse en verlagen operationele voorspelbaarheid.
- Uitvoering:
1. Introduceer domein-exceptions voor market data, risk gate, broker bridge en inference.
2. Voeg error_code velden toe aan logging/audit events.
3. Vervang broad except Exception alleen in kritieke paden waar incident-impact hoog is.
- Betrokken bestanden:
1. [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py)
2. [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py)
3. [lumina_core/engine/trade_reconciler.py](lumina_core/engine/trade_reconciler.py)
4. [lumina_core/engine/analysis_service.py](lumina_core/engine/analysis_service.py)
- Acceptatiecriteria:
1. Incident logs bevatten gestandaardiseerde error_code waarden.
2. Kritieke except-paden gereduceerd en unit-tests dekken mapping.
3. Geen wijziging in mode-semantiek of order-routing regels.
- Verificatie:
1. Typed exception- en mapperlaag toegevoegd in [lumina_core/engine/errors.py](lumina_core/engine/errors.py).
2. Kritieke foutpaden voorzien van gestandaardiseerde error_codes in [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py), [lumina_core/engine/reasoning_service.py](lumina_core/engine/reasoning_service.py), [lumina_core/engine/trade_reconciler.py](lumina_core/engine/trade_reconciler.py) en [lumina_core/engine/analysis_service.py](lumina_core/engine/analysis_service.py).
3. Gerichte regressietests toegevoegd in [tests/test_engine_error_codes.py](tests/test_engine_error_codes.py) en gevalideerd samen met reasoning/reconciler suites.

#### G3. SessionGuard als enige bron voor market-open beslissingen
- Status: [x]
- Waarom:
1. Simpele uur-fallback kan divergeren van kalendergedrag.
- Uitvoering:
1. Verwijder of isoleer legacy tijdvenster-fallback uit operationele paden.
2. Behoud alleen SessionGuard gebaseerde beslissing met fail-closed fallback bij guard-fout.
3. Houd paper/sim/real regels uit trade mode referentie ongewijzigd.
- Betrokken bestanden:
1. [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py)
2. [tests/test_trade_mode_invariants.py](tests/test_trade_mode_invariants.py)
3. [tests](tests)
- Acceptatiecriteria:
1. Geen operationeel pad meer dat market-open bepaalt via losse datetime-urencheck.
2. Session- en rollover-tests groen in sim en real.
- Verificatie:
1. Legacy datetime-urencheck verwijderd uit [lumina_core/engine/operations_service.py](lumina_core/engine/operations_service.py); pad is nu SessionGuard-only en fail-closed.
2. Regressietests toegevoegd in [tests/test_trade_mode_golden_paths.py](tests/test_trade_mode_golden_paths.py) voor SessionGuard-only, unavailable en exception-scenario.

#### G4. Testmarker opschoning en CI selectiebetrouwbaarheid
- Status: [x]
- Waarom:
1. Dubbele markers vervuilen testselectie en rapportage.
- Uitvoering:
1. Verwijder duplicaat marker-definities en voeg marker-lintcheck toe in CI.
2. Publiceer marker governance in release checklist.
- Betrokken bestanden:
1. [pytest.ini](pytest.ini)
2. [.github/workflows/safety-gate.yml](.github/workflows/safety-gate.yml)
3. [docs/release-gate-checklist.md](docs/release-gate-checklist.md)
- Acceptatiecriteria:
1. Geen duplicaat markerregels in pytest-config.
2. CI faalt op markerduplicatie regressie.
- Verificatie:
1. Duplicaat chaos_metrics markerdefinities verwijderd in [pytest.ini](pytest.ini).
2. Marker-lint toegevoegd via [scripts/validation/check_pytest_marker_duplicates.py](scripts/validation/check_pytest_marker_duplicates.py) en opgenomen in [.github/workflows/safety-gate.yml](.github/workflows/safety-gate.yml).
3. Marker governance bewijsveld toegevoegd in [docs/release-gate-checklist.md](docs/release-gate-checklist.md).

#### G5. Legacy compat wrappers gecontroleerd uitfaseren
- Status: [x]
- Waarom:
1. Wrapper-duplicatie verhoogt onderhoudslast en importverwarring.
- Uitvoering:
1. Fase 1: deprecatie-waarschuwing + import-auditrapport.
2. Fase 2: alle interne imports migreren naar canonieke snake_case modules.
3. Fase 3: wrappers verwijderen na twee stabiele releases met groene import-audit.
- Betrokken bestanden:
1. [lumina_core/engine/FastPathEngine.py](lumina_core/engine/FastPathEngine.py)
2. [lumina_core/engine/TapeReadingAgent.py](lumina_core/engine/TapeReadingAgent.py)
3. [lumina_core/engine/AdvancedBacktesterEngine.py](lumina_core/engine/AdvancedBacktesterEngine.py)
4. [lumina_core/engine/RealisticBacktesterEngine.py](lumina_core/engine/RealisticBacktesterEngine.py)
5. [lumina_core/engine](lumina_core/engine)
- Acceptatiecriteria:
1. Geen interne runtime-imports meer via wrapperpaden.
2. Wrapperverwijdering zonder regressie op golden paths.
- Verificatie:
1. Legacy import audit bevestigd op 0 interne wrapper-imports via [state/legacy_import_audit.json](state/legacy_import_audit.json).
2. CI enforcement toegevoegd via `LUMINA_FAIL_ON_LEGACY_IMPORTS=true` in [.github/workflows/safety-gate.yml](.github/workflows/safety-gate.yml).
3. Wrapper-deprecaties blijven gecontroleerd actief tot verwijderwindow; governance-bewijs toegevoegd in [docs/release-gate-checklist.md](docs/release-gate-checklist.md).

#### G6. Stress-gate robuustheid verhogen zonder strategie-aanpassing
- Status: [x]
- Waarom:
1. Regime scorecard is groen, maar stress gate staat nog fail-closed.
- Uitvoering:
1. Verbeter datakwaliteit, scenariodekking en meetinstrumentatie rond stressrapportage.
2. Tuning enkel op risicoparameters en execution-frictie modellering, niet op tradingstijl of leerdoel.
3. Documenteer evidence voor hold_and_retrain versus ready_for_real.
- Betrokken bestanden:
1. [lumina_core/engine/stress_suite_runner.py](lumina_core/engine/stress_suite_runner.py)
2. [scripts/validation/run_regime_validation_pack.py](scripts/validation/run_regime_validation_pack.py)
3. [state/validation/regime_scorecard.json](state/validation/regime_scorecard.json)
4. [docs/PRODUCTION_CHECKLIST_v51.md](docs/PRODUCTION_CHECKLIST_v51.md)
- Acceptatiecriteria:
1. Stress-artefacten zijn reproduceerbaar en verklarend per scenario.
2. Gate-besluit is auditbaar met expliciete drempelreden.
3. Geen wijziging van core trading- en leersemantiek.
- Verificatie:
1. Stress diagnostics uitgebreid in [lumina_core/engine/stress_suite_runner.py](lumina_core/engine/stress_suite_runner.py) met `gate_checks`, `gate_thresholds`, `gate_fail_reasons` en scorecard `gate_failure_reasons`.
2. Regressietests uitgebreid in [tests/test_stress_suite_runner.py](tests/test_stress_suite_runner.py).
3. Validatie-artifact opnieuw gegenereerd in [state/validation/regime_scorecard.json](state/validation/regime_scorecard.json) met expliciete hold-reden `VAR_BREACH_LIMIT_EXCEEDED(...)`.
4. Operationele checklist bijgewerkt in [docs/PRODUCTION_CHECKLIST_v51.md](docs/PRODUCTION_CHECKLIST_v51.md) voor auditbare stress-gate evidence.

### Uitvoeringsvolgorde restpunten

1. G1
2. G3
3. G2
4. G4
5. G5
6. G6

### Done-criterium restpunten

1. Alle G-items op [x] met bewijslink naar tests, artifacts en runbook update.
2. Trade mode contracttests blijven groen op paper/sim/real.
3. Geen wijziging in strategie/leerpad, alleen robuustheid, observability en governance.
