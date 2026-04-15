ja commit and# Lumina - Correctieplan Expert 3 (Innovatief, Functioneel Behoud)

Datum: 2026-04-10  
Doel: de Expert-3 zwakke punten oplossen met een vernieuwende, schaalbare aanpak zonder de kerndoelen of app-functies te wijzigen.  
Principe: niets is onmogelijk; alles wordt opgesplitst in kleine, verifieerbare stappen die samen een robuust geheel vormen.

---

## 0. Harde Invarianten (Niet Onderhandelbaar)

Deze invarianten blijven exact behouden tijdens alle verbeteringen:

1. paper-mode:
- Geen broker-call
- `place_order()` retourneert `False`
- Fills/PnL intern via supervisor-loop

2. sim-mode:
- Live marktdata + live broker op sim-account
- SessionGuard actief
- HardRiskController advisory (`enforce_rules=False`)

3. real-mode:
- Live broker op real-account
- SessionGuard + HardRiskController volledig fail-closed

4. App-doel blijft identiek:
- Geen wijziging in fundamentele missie (AI-gedreven trading bot)
- Geen wijziging in kernfunctionaliteiten, alleen governance, helderheid en betrouwbaarheid

5. Elke fase moet aantonen:
- geen functionele regressie
- trade-mode semantiek ongewijzigd
- tests groen

---

## 1. Zeer Grondige Analyse Per Zwak Punt

## 1.1 Mode-semantiek sim/paper/real is operationeel verwarrend (Critical)

Observatie:
- Trade-mode referentie is helder, maar operationele interpretatie kan alsnog afwijken wanneer `trade_mode` en `broker_backend` op verschillende plaatsen worden afgeleid.
- In `EngineConfig` zitten afleidingspaden die verwarring kunnen veroorzaken zonder expliciete incompatibiliteits-checks.

Risico:
- Foutieve combinatie (`trade_mode=paper` + `broker_backend=live`) kan operators misleiden.
- Runbook-interpretatie kan divergeren van runtime-gedrag.

Strategische oplossing:
- Introduceer een canonical mode matrix resolver:
  - input: `trade_mode`, `broker_backend`, env overrides
  - output: gevalideerde runtime intent (`paper|sim|real`) + execution intent (`paper|live`)
- Voeg startup hard-validation toe op ongeldige combinaties.
- Maak de matrix zichtbaar in startup logs (effective configuration report).

---

## 1.2 Simulatie- en leerboost kunnen te optimistische edge-signalen geven (High)

Observatie:
- Headless sim bevat expliciete learning shaping (winstversterking/verliesdemping in sim-learning context).
- Dit is legitiem voor exploratie, maar kan rapportering beïnvloeden als metrics niet strikt gescheiden zijn.

Risico:
- Verwarring tussen “learning fitness” en “execution realism”.
- Onjuiste verwachtingen bij operatorbeslissingen.

Strategische oplossing:
- Introduceer dual-metric model:
  - Learning Metrics: exploration/reward shaping
  - Realism Metrics: execution-consistente PnL/Sharpe/expectancy
- Beide verplicht rapporteren in headless summary + dashboards.
- Voeg expliciete labeling toe in elke output en runbook.

---

## 1.3 Live uitvoeringspad en risk-paden niet volledig geharmoniseerd (Critical)

Observatie:
- Er zijn meerdere paden die orderbeslissingen raken (runtime workers, trade workers, operations service, broker bridge).
- Hoewel verbeterd, blijft risico op toekomstige divergentie bestaan als entry-point niet centraal gecontracteerd is.

Risico:
- Inconsistent pre-trade checks per pad.
- Moeilijker formeel aantonen dat elk order identiek door risk gates ging.

Strategische oplossing:
- Definieer een enkele Order Gatekeeper API (service contract):
  - pre-trade checks (session/risk/mode)
  - submit
  - post-trade audit event
- Laat andere paden adapters zijn die altijd deze gatekeeper aanroepen.
- Voeg contract-tests toe die afdwingen dat alle orderpaden dezelfde gate gebruiken.

---

## 1.4 News-agent afhankelijkheid van externe provider (Medium)

Observatie:
- Externe provider uitval/latency is onvermijdelijk.
- Zonder sterk fallback-regime kan output te veel HOLD of stale sentiment geven.

Risico:
- Instabiele besluitvorming tijdens providerproblemen.
- Stil degradatiegedrag zonder duidelijke operator-signalen.

Strategische oplossing:
- Voeg expliciet fallback ladder-model toe:
  1. primary provider
  2. cached recent sentiment (met TTL)
  3. lokale heuristiek (event calendar + volatility proxy)
  4. fail-safe mode (HOLD met reason code)
- Verplicht reason-code logging per fallback niveau.
- Voeg recency-expiry hard-check toe (stale data mag niet als vers worden behandeld).

---

## 1.5 Swarm-arbitrage op eenvoudige z-score zonder transactiekostmodel (Medium)

Observatie:
- Z-score alleen is onvoldoende voor live executability.
- Execution costs en slippage regime bepalen of edge netto positief blijft.

Risico:
- Overtrading op statistisch signaal dat netto negatief is na kosten.
- Te hoge trade-frequentie in lage-edge omgevingen.

Strategische oplossing:
- Voeg net-edge filter toe vóór order:
  - expected_gross_edge
  - expected_cost (commission + slippage regime)
  - expected_net_edge = gross - cost
- Alleen handelen bij net_edge > minimum threshold.
- Threshold regime-aware maken (volatility/liquidity state).

---

## 2. Wat Moet Verwijderd Worden (Expert 3)

1. Impliciete/ambigue mode-claims in docs die niet 1-op-1 met runtime afdwinging overeenkomen.
2. Niet-gedifferentieerde rapportering waarin sim learning shaping en realistische PnL door elkaar staan.

Aanpak:
- Document governance pass:
  - alle mode-claims in docs vergelijken met canonical mode matrix
  - mismatch -> corrigeren
- Reporting governance pass:
  - iedere sim-output krijgt dual-metric labels (learning vs realism)
  - legacy gemengde metricpresentaties verwijderen

---

## 3. Innovatief Uitvoeringsplan in Kleine Bouwblokken

### Fase A - Canonical Contract Layer
1. Definieer `ModeMatrixContract` (input/output + validatieregels).
2. Definieer `OrderGatekeeperContract` (pre/post conditions).
3. Definieer `SimulationMetricsContract` (learning vs realism).

Deliverable:
- Drie expliciete contracten met tests (nog zonder gedrag te wijzigen).

### Fase B - Runtime Enforcement
1. Implementeer mode matrix resolver en startup hard-validation.
2. Laat startup effective mode report printen.
3. Maak alle order entrypoints afhankelijk van GatekeeperContract.

Deliverable:
- Runtime gebruikt contracten als verplichte route.

### Fase C - Simulation Realism Separation
1. Label bestaande sim-shaping metrics als learning.
2. Voeg realism metrics toe op dezelfde run.
3. Output dual metrics naar JSON summary en dashboards.

Deliverable:
- Operator ziet twee consistente performancebeelden per run.

### Fase D - News Resilience Upgrade
1. Fallback ladder implementeren met TTL/expiry.
2. Reason-code logging verplicht.
3. Alerting toevoegen bij fallback niveau 3/4.

Deliverable:
- Robuuste degradatie zonder “silent stale behavior”.

### Fase E - Swarm Net-Edge Gate
1. Kostenmodel integreren in swarm trigger.
2. Net-edge threshold regime-aware maken.
3. Backtest/sim validatie op trade reduction vs expectancy uplift.

Deliverable:
- Minder overtrading, hogere netto-signaalkwaliteit.

### Fase F - Documentation Purge + Operational Readiness
1. Ambigue mode-claims verwijderen/corrigeren.
2. Gemengde sim-metric rapportering opschonen.
3. Runbook update met expliciete interpretatieregels.

Deliverable:
- 1-op-1 alignment tussen docs, runtime en operatorbeslissingen.

---

## 4. Gedetailleerde Todo List

| # | Taak | Prioriteit | Status |
|---|---|---|---|
| 1 | Inventaris van alle mode-afleidingen (`trade_mode`, `broker_backend`, env) | Critical | Klaar |
| 2 | Ontwerp + tests voor canonical mode matrix contract | Critical | Klaar |
| 3 | Startup hard-validation voor ongeldige mode/backend combinaties | Critical | Klaar |
| 4 | Ontwerp + tests voor Order Gatekeeper contract | Critical | Klaar |
| 5 | Routering van alle orderpaden via 1 gatekeeper | Critical | Klaar |
| 6 | Ontwerp dual metrics contract (learning vs realism) | High | Klaar |
| 7 | Headless summary uitbreiden met dual metrics labeling | High | Klaar |
| 8 | Dashboard/runbook labels aanpassen voor metric-separatie | High | Klaar |
| 9 | News fallback ladder + reason codes + TTL expiry | Medium | Klaar |
| 10 | Swarm net-edge filter met kosten/slippage regime | Medium | Klaar |
| 11 | Opschonen ambigue mode-claims in docs | Medium | Klaar |
| 12 | Opschonen gemengde sim/realism rapportering | Medium | Klaar |
| 13 | Volledige regressie + parity checks paper/sim/real | Critical | Klaar |
| 14 | Eindrapport met bewijs van non-regression | Critical | Klaar |

---

## 9. Uitvoeringsextract (2026-04-10)

Gerealiseerde wijzigingen:

1. Mode matrix enforcement
- `ConfigLoader.validate_startup` valideert nu hard op combinatie:
  - `paper` alleen met `paper` backend
  - `sim|real` alleen met `live` backend

2. Centrale order gatekeeper
- Nieuw: `lumina_core/order_gatekeeper.py`
- `trade_workers.check_pre_trade_risk` en `OperationsService.place_order` lopen via dezelfde gate.

3. Dual simulation metrics
- `HeadlessRuntime` rapporteert zowel `metrics_learning` als `metrics_realism`.
- Top-level output blijft backward compatible met bestaande SIM-learning workflow.

4. News fallback ladder
- Toegevoegd: fallback niveaus, reason-codes, cache TTL recency gedrag.

5. Swarm net-edge filter
- Arbitrage-signalen vereisen nu positieve netto-edge na kostenmodel.

Testbewijs:
- Gerichte regressie: `77 passed`
- Volledige regressie: `311 passed, 2 skipped`

---

## 5. Validatieplan (Bewijs dat functies gelijk blijven)

Verplicht na elke fase:

1. Mode parity checks:
- paper: return False, geen broker call
- sim: live + SessionGuard + advisory risk
- real: live + SessionGuard + full fail-closed risk

2. Regressie checks:
- order path regressietests
- broker bridge tests
- full test suite

3. Safety checks:
- geen bypass van gatekeeper
- geen ongedocumenteerde fallback
- geen ambigue mode-claims in docs

4. Metrics checks:
- learning en realism metrics bestaan beide
- labels zijn expliciet en niet gemengd

---

## 6. Definition of Done

Deze Expert-3 verbetertrack is pas klaar als:

1. De vijf zwakke punten functioneel zijn aangepakt.
2. Beide verwijderpunten daadwerkelijk zijn opgeschoond.
3. Trade-mode referentie exact behouden is.
4. App-doel en kernfunctionaliteit ongewijzigd zijn.
5. Alle relevante tests groen zijn.
6. Documentatie, runtime en operator-runbook 1-op-1 overeenkomen.

---

## 7. Uitvoeringsvolgorde (Snelste pad met laagste risico)

1. Mode matrix contract + startup validation
2. Order gatekeeper centralisatie
3. Dual metrics separation (learning vs realism)
4. News fallback ladder
5. Swarm net-edge filter
6. Doc/reporting cleanup
7. End-to-end regressie + eindrapport

---

## 8. Kernboodschap

Deze aanpak behandelt de bot als een high-innovation systeem: niet beperken op ambitie, maar ambitie in modules opdelen die elk verifieerbaar zijn. Zo bouwen we vernieuwend en veilig tegelijk: grote sprong, kleine gecontroleerde stappen, en uiteindelijk 1 coherent geheel.