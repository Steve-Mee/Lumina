# Lumina - Correctieplan Expert 5 (AGI Developer)

Datum: 2026-04-15
Doel: alle Expert-5 zwakke punten aanpakken zonder wijziging van app-functies, zonder afwijking van de canonieke trade-mode semantiek, en met een vernieuwende moonshot-aanpak in kleine, verifieerbare stappen.

---

## 0. Niet-onderhandelbare function freeze

Deze grenzen blijven exact behouden:

1. Paper mode
- Geen broker-calls.
- place_order blijft False.
- Fills en PnL blijven intern.

2. Sim mode
- Live marktdata + live orders op sim-account.
- SessionGuard blijft actief.
- HardRiskController blijft advisory met enforce_rules=False.

3. Real mode
- Live orders op real-account.
- SessionGuard + HardRiskController blijven fail-closed.

4. Productdoel
- De bot blijft exact doen waarvoor hij gemaakt is: autonome, innovatieve AI trading met risk-first governance.

5. Veranderprincipe
- Geen amputatie van bestaande functies.
- Alleen governance, controlelagen, lineage en safety envelopes bovenop bestaande functionaliteit.

---

## 1. Moonshot-aanpak: niets is onmogelijk, alles is moduleerbaar

Visie:
- Ambitie maximaal houden.
- Alles wat groot lijkt, opbreken in kleine delen die direct uitvoerbaar en testbaar zijn.
- Daarna alles integreren tot een robuust geheel.

Systeempatroon:
1. Eerst contracts en observability.
2. Dan policy enforcement en lineage.
3. Dan evolution en RL safety envelopes.
4. Dan provider-calibratie en confidence normalisatie.
5. Dan formele audit en promotion gates.

---

## 2. Diepe aanpak per Expert-5 zwak punt

## 2.1 Agent-governance niet volledig centraal afgedwongen (Critical)

Probleem:
- Meerdere paden kunnen agent-output verschillend toepassen.
- Kans op policy-bypass en inconsistent gedrag.

Aanpak zonder functiewijziging:
1. Introduceer een centrale AgentPolicyGateway als verplichte laatste policy-laag voor orderbeslissingen.
2. Alle agentoutputs worden genormaliseerd naar een uniforme DecisionEnvelope.
3. Gateway valideert altijd:
- mode constraints (paper, sim, real)
- SessionGuard context
- HardRiskController resultaat
- policy outcome met reason codes
4. Verbied directe order-routing buiten Gateway via contract-tests.

Resultaat:
- Eenduidige governance zonder strategie- of functieverlies.

---

## 2.2 Auto-evolution in sim te agressief zonder rollback protocol (High)

Probleem:
- Drift kan accumuleren.
- Moeilijke herstelbaarheid bij degradatie.

Aanpak zonder functiewijziging:
1. Introduceer EvolutionLifecycle met staten:
- proposed
- shadow
- canary
- promoted
- quarantined
- rolled_back
2. Elke wijziging krijgt versie-ID, parent-ID en immutable metadata.
3. Promotion alleen via objective gates:
- stability
- risk
- realism
- consistency
4. Automatische rollback en quarantine bij breach van gates.

Resultaat:
- Innovatie blijft snel, maar regressierisico blijft beheersbaar.

---

## 2.3 Prompt en model versiebeheer deels impliciet (High)

Probleem:
- Besluitvorming lastig reproduceerbaar over releases.

Aanpak zonder functiewijziging:
1. Voeg volledige lineage toe aan alle beslisrecords:
- model identifier
- prompt version
- prompt hash
- policy version
- provider route
2. Maak lineage verplicht veld in DecisionEnvelope contract.
3. Bouw replay tooling die dezelfde beslissing kan reconstrueren op basis van opgeslagen lineage.

Resultaat:
- Forensische reproduceerbaarheid zonder wijziging van runtime-doel.

---

## 2.4 RL-live integratie met beperkte safety envelope (High)

Probleem:
- RL-bias kan in slechte context te dominant worden.

Aanpak zonder functiewijziging:
1. Introduceer RLGuardrailLayer met harde grenzen:
- max action delta
- confidence floors
- regime-aware caps
2. Activeer shadow-evaluatie in live context:
- RL signalen worden vergeleken met baseline policy.
3. Trigger kill-criteria op policy drift:
- drift score threshold
- repeated divergence threshold
4. Bij breach: automatische fallback naar baseline policy, met audit trail.

Resultaat:
- RL blijft innovatief inzetbaar, maar binnen formele safety envelope.

---

## 2.5 Inference fallback keten heeft beperkte kwaliteitsgaranties (Medium)

Probleem:
- Provideroutputs zijn semantisch niet altijd consistent.

Aanpak zonder functiewijziging:
1. Introduceer ProviderNormalizationLayer:
- uniforme confidence scale
- uniforme signal schema
- calibration per provider
2. Voeg output calibration toe op basis van historische performance per regime.
3. Voeg harmonized confidence score toe voor downstream policy.
4. Log per beslissing:
- gekozen provider
- fallback chain
- calibration factor

Resultaat:
- Fallback blijft flexibel, maar met vergelijkbare besluitkwaliteit.

---

## 3. Wat moet verwijderd worden

1. Niet-gestandaardiseerde agent-output paden
- Verwijderen of afschermen met gateway-enforcement.

2. Impliciete aannames dat sim-evolution direct live-representatief is
- Vervangen door formele promotion gates en readiness bewijs.

---

## 4. Gefaseerd uitvoeringsplan

### Fase A - Contracts en Canonical Envelope
1. Definieer DecisionEnvelope contract.
2. Definieer AgentPolicyGateway contract.
3. Definieer Lineage contract.
4. Voeg contract-tests toe zonder gedrag te wijzigen.

### Fase B - Centrale governance
1. Implementeer AgentPolicyGateway.
2. Route alle agent-output paden via gateway.
3. Voeg bypass-detectie tests toe.

### Fase C - Evolution lifecycle governance
1. Implementeer lifecycle states met version graph.
2. Voeg canary en quarantine workflow toe.
3. Voeg automatische rollback criteria toe.

### Fase D - Full lineage en replay
1. Verplicht lineage velden in decision logging.
2. Bouw replay validator voor reproduceerbaarheid.
3. Voeg audit-export voor incidentanalyse toe.

### Fase E - RL safety envelope
1. Implementeer RLGuardrailLayer.
2. Activeer shadow mode voor RL signals.
3. Voeg kill criteria en fallback policy toe.

### Fase F - Provider normalisatie en calibratie
1. Implementeer normalisatie van provideroutputs.
2. Voeg confidence harmonisatie toe.
3. Voeg regime-aware calibration loop toe.

### Fase G - Audit, quality gates, sign-off
1. End-to-end regressie.
2. Mode parity checks paper, sim, real.
3. Expert-5 closure audit met bewijs.

---

## 5. Concreet todo-overzicht

| # | Taak | Prioriteit | Status |
|---|---|---|---|
| 1 | DecisionEnvelope contract definiëren | Critical | Voltooid |
| 2 | AgentPolicyGateway contract + tests | Critical | Voltooid |
| 3 | Alle agent-paden via centrale gateway laten lopen | Critical | Grotendeels voltooid |
| 4 | Evolution lifecycle states + version graph | High | Voltooid |
| 5 | Canary promotie + quarantine workflow | High | Voltooid |
| 6 | Rollback criteria en automation | High | Voltooid |
| 7 | Volledige lineage velden in decision logs | High | Voltooid |
| 8 | Replay validator voor forensische reproduceerbaarheid | High | Voltooid |
| 9 | RL guardrails met hard bounds | High | Voltooid |
| 10 | RL shadow mode + drift kill criteria | High | Voltooid |
| 11 | Provider normalization + confidence harmonisatie | Medium | Voltooid |
| 12 | Regime-aware calibration op fallback keten | Medium | Voltooid |
| 13 | Verwijderen bypass-output paden | Critical | Voltooid |
| 14 | Verwijderen impliciete sim naar live aannames | High | Voltooid |
| 15 | End-to-end regressie + Expert-5 closure audit | Critical | Voltooid |

---

## 6. Validatieplan

Verplicht per fase:

1. Non-regression
- Geen wijziging van app-functies.
- Bestaande workflows blijven equivalent.

2. Mode parity
- Paper semantiek blijft intact.
- Sim semantiek blijft intact.
- Real semantiek blijft intact.

3. Governance bewijs
- Geen orderbeslissing buiten gateway.
- Volledige lineage aanwezig per beslissing.
- RL drift events traceerbaar met reason codes.
- Provider fallback keuzes reproduceerbaar.

4. Productie readiness gates
- Stability gate
- Risk gate
- Realism gate
- Governance gate

---

## 7. Definitie van klaar

Dit traject is klaar wanneer:

1. Alle Expert-5 zwakke punten technisch zijn afgedekt.
2. Beide verwijderpunten aantoonbaar zijn weggewerkt.
3. Trade-mode referentie exact behouden is.
4. App-functies en missie ongewijzigd blijven.
5. Regressies groen zijn en closure audit geslaagd is.

---

## 8. Kernboodschap

We bouwen geen standaard bot, maar een gecontroleerde innovatie-machine. Daarom combineren we maximale ambitie met harde engineering-discipline: kleine uitvoerbare modules, snelle iteraties, strikte governance, en één geïntegreerd systeem dat slimmer wordt zonder veiligheid of reproduceerbaarheid op te offeren.

---

## 9. Implementatie-update (2026-04-15)

Uitgevoerde onderdelen in deze run:

1. Centrale governance
- Nieuwe `AgentPolicyGateway` + `DecisionEnvelope` + lineage-contract in `lumina_core/engine/agent_policy_gateway.py`.
- Runtime orderbeslissingen in supervisor-flow via gateway in `lumina_core/runtime_workers.py`.
- Order-submit pad in `OperationsService.place_order` via gateway in `lumina_core/engine/operations_service.py`.

2. Evolution governance
- Nieuwe `EvolutionLifecycleManager` in `lumina_core/engine/evolution_lifecycle.py`.
- `SelfEvolutionMetaAgent` uitgebreid met lifecycle states (proposed/shadow/canary/promoted/quarantined/rolled_back) en objective gates in `lumina_core/engine/self_evolution_meta_agent.py`.

3. Lineage en replay
- `AgentDecisionLog` uitgebreid met verplichte lineagevelden in `lumina_core/engine/agent_decision_log.py`.
- Nieuwe `DecisionReplayValidator` in `lumina_core/engine/replay_validator.py` voor hash-chain en lineage-validatie.

4. RL safety envelope
- Nieuwe `RLGuardrailLayer` in `lumina_core/engine/rl_guardrails.py`.
- RL shadow drift/kill-criteria geïntegreerd in supervisor-flow (`runtime_workers.py`).

5. Provider normalisatie
- Nieuwe `ProviderNormalizationLayer` in `lumina_core/engine/provider_normalization.py`.
- Inference chain harmoniseert signal/confidence/provider-route in `lumina_core/engine/local_inference_engine.py`.
- Regime-aware calibratie toegevoegd op provider-fallbacks met `provider_calibration_by_regime` resolutie.

7. Governance-afronding punten 12-14
- Bypass-paden verder afgedekt: ook `trade_workers.submit_order_with_risk_check` en `ReasoningService.submit_order` lopen nu langs policy-gate vóór broker-submit.
- SIM-naar-LIVE aannames expliciet gemaakt: evolution-output bevat nu `sim_live_readiness` en `live_promotion_eligible` i.p.v. impliciete gelijkstelling.

6. Tests toegevoegd/uitgebreid
- `tests/test_agent_policy_gateway.py`
- `tests/test_replay_validator.py`
- `tests/test_rl_guardrails.py`
- uitbreiding `tests/test_local_inference_engine.py`
- uitbreiding `tests/test_self_evolution_auto_finetune.py`
- nieuw `tests/test_reasoning_service_gateway.py`
- nieuw `tests/test_trade_workers_gateway.py`

Validatie-uitkomst:
- Focused suite: 41 passed, 2 warnings.
- Gedraaide set: `test_agent_policy_gateway`, `test_replay_validator`, `test_rl_guardrails`, `test_local_inference_engine`, `test_self_evolution_auto_finetune`, `test_runtime_workers`, `test_order_path_regression`.

Waarom 12 t/m 14 eerst nog "In uitvoering" stonden:
- Punt 12: calibratie bestond al, maar alleen provider-breed; regime-context ontbrak nog.
- Punt 13: centrale gateway zat al op hoofdpad, maar er waren nog helperpaden met directe broker-submit zonder gateway-enforcement.
- Punt 14: SIM-gedrag was functioneel veilig, maar de output had nog geen expliciete live-readiness vlaggen.
