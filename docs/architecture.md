# LUMINA — Architecture Overview

> **Mission-aligned.** Dit document beschrijft hoe Lumina als systeem is opgebouwd: een **levend organisme** dat leert, muteert en handelt — met harde veiligheidsgrenzen voordat echte kapitaalstromen worden geraakt.

---

## 1. Inleiding

LUMINA is geen statische rule-set: het is een **zelflerend, zelf-evoluerend** trading-organisme dat op NinjaTrader draait en continu probeert te behoren tot de **1%** die structureel overleeft — niet door geluk, maar door architectuur.

Drie principes vormen het ruggengraat:

| Principe | Wat het betekent in Lumina |
|----------|------------------------------|
| **Safety First** | In **REAL** mode is kapitaalbehoud heilig: mutaties, promoties en orders gaan door constitutionele checks, sandboxing en shadow gates voordat ze live impact krijgen. In **SIM/PAPER** mag het organisme radicaal experimenteren binnen fysieke grenzen. |
| **Self-Evolving** | DNA-mutaties, parallel realities en meta-agents laten het systeem zich aanpassen — maar **niet** zonder de safety-laag en observeerbare feedback (metrics, audit, blackboard). |
| **Intellectual Honesty** | Geen optimisme over backtests of risico: beslissingen zijn traceerbaar, principes zijn machine-enforced waar mogelijk, en architectuurkeuzes worden **ADR-gedreven** vastgelegd. |

Samengevat: Lumina **ademt** marktdata in, **denkt** via engine en agents, **muteert** in evolution — en **sluit** af als iets de Noordster bedreigt.

---

## 2. High-Level Architecture

De stack is bewust **top-down**: eerst wat het systeem **niet** mag breken, dan hoe het **leren** gebeurt, dan **handelen** en **risico** aan de onderkant.

```mermaid
flowchart TB
    subgraph safetyLayer [Safety Layer]
        constitution[Constitution]
        sandbox[Sandbox]
        shadow[Shadow Deployment]
    end

    subgraph evolutionLayer [Evolution Layer]
        parallel[Parallel Realities]
        meta[Meta Agent]
        blackboard[Blackboard]
    end

    subgraph tradingEngine [Trading Engine]
        bounded[Bounded Contexts]
        eventBus[Event Bus]
    end

    subgraph riskExec [Risk plus Execution]
        riskCtrl[Risk Controller]
        execution[Execution]
    end

    safetyLayer --> evolutionLayer
    evolutionLayer --> tradingEngine
    tradingEngine --> riskExec
```

**Leesrichting:** veiligheid en observability gaan **voor** evolutie; de trading engine coördineert domeinen via events; risk en execution zijn de laatste poorten naar de markt.

---

## 3. Bounded Contexts Overzicht

LUMINA gebruikt **bounded contexts** als domeingrenzen onder `lumina_core/` (zie [ADR 0001](adr/0001-bounded-contexts-central-event-bus.md)). Context-overstijgende signalen lopen waar mogelijk via de centrale **Event Bus** — niet via onbeperkte cross-imports.

| Context | Verantwoordelijkheid | Primaire paden | Opmerking |
|---------|---------------------|----------------|-----------|
| **Safety** | Constitutionele principes, sandboxed uitvoering, promotion gates | [`lumina_core/safety/`](../lumina_core/safety/) | Fail-closed; REAL strengst |
| **Evolution** | DNA, orchestratie, shadow runs, fitness | [`lumina_core/evolution/`](../lumina_core/evolution/) | SIM kan agressiever; REAL vereist shadow + approval waar van toepassing |
| **Trading Engine** | Kern trading: engine, marktdata, operaties, valuation | [`lumina_core/trading_engine/`](../lumina_core/trading_engine/), [`lumina_core/engine/`](../lumina_core/engine/) | `engine/` bevat nog veel legacy surface; migratie is geleidelijk |
| **Risk Management** | Risk gates, allocatie, Kelly-achtige begrenzing | [`lumina_core/risk/`](../lumina_core/risk/) | Via mixins/engine geïntegreerd; canoniek onder `risk/` |
| **Agent Orchestration** | Event bus, engine↔blackboard bindingen | [`lumina_core/agent_orchestration/`](../lumina_core/agent_orchestration/) | Pub/sub en bindings centraliseren |

```mermaid
flowchart LR
    subgraph contexts [Bounded contexts]
        safetyCtx[Safety]
        evolutionCtx[Evolution]
        tradingCtx[TradingEngine]
        riskCtx[RiskManagement]
        orchCtx[AgentOrchestration]
    end

    eventBusNode[EventBus]

    tradingCtx -->|"publish domain events"| eventBusNode
    orchCtx -->|"subscribe route"| eventBusNode
    evolutionCtx -->|"observe evolve"| eventBusNode
    riskCtx -->|"gates sizing"| tradingCtx
    safetyCtx -->|"veto gate"| evolutionCtx
    safetyCtx -->|"principles"| tradingCtx
```

### 3.1 Evolution-laag componenten

`lumina_core/evolution/evolution_orchestrator.py` is nu een dunne compatibiliteitslaag. De implementatie is opgesplitst in losse eenheden met expliciete contracts zodat mutation, fitness en promotion afzonderlijk getest kunnen worden.

```mermaid
flowchart LR
    compatLayer[evolution_orchestrator.py]
    orchestratorComp[orchestrator.py]
    fitnessComp[fitness_evaluator.py]
    mutationComp[mutation_pipeline.py]
    promotionComp[promotion_policy.py]

    compatLayer --> orchestratorComp
    compatLayer --> fitnessComp
    compatLayer --> mutationComp
    orchestratorComp --> fitnessComp
    orchestratorComp --> mutationComp
    orchestratorComp --> promotionComp
```

- `orchestrator.py` bewaart een backward-compatible exportlaag voor bestaande imports.
- `orchestrator_core.py` bevat `EvolutionOrchestrator` + generation-coordinatie en runtime wiring.
- `fitness_evaluator.py` bevat deterministische score- en seedlogica voor kandidaten.
- `mutation_pipeline.py` bevat candidate-generatie + bootstrap via een protocolgestuurde pipeline.
- `promotion_policy.py` bevat shadow-run policy, veto-window checks en promotion-statusafhandeling.
- `evolution_orchestrator.py` blijft import-stabiel voor bestaande callers en test monkeypatches.

### 3.2 Self-evolution meta-agent componenten

`lumina_core/engine/self_evolution_meta_agent.py` is nu een dunne compatibiliteitslaag. De implementatie is opgesplitst in losse modules zodat proposal-generatie, anomaliedetectie en auditlogica apart testbaar zijn.

```mermaid
flowchart LR
    compatMeta[self_evolution_meta_agent.py]
    metaCore[meta_agent.py]
    proposalCore[proposal_generator.py]
    anomalyCore[anomaly_detector.py]
    auditCore[audit_writer.py]

    compatMeta --> metaCore
    metaCore --> proposalCore
    metaCore --> anomalyCore
    metaCore --> auditCore
```

- `meta_agent.py` bewaart een backward-compatible exportlaag voor bestaande imports.
- `meta_agent_core.py` houdt de `SelfEvolutionMetaAgent` orchestratie en runtime flow.
- `proposal_generator.py` bevat challenger/genetic candidate-opbouw en DNA-registratie.
- `anomaly_detector.py` bevat drift/acceptance meta-review en auto-fine-tune triggers.
- `audit_writer.py` beheert append-only hash-chained evolution logging en decision-log forwarding.
- `self_evolution_meta_agent.py` bewaart backward-compatible imports voor bestaande callers en tests.

### 3.3 Dashboard componenten

`lumina_core/engine/dashboard_service.py` is nu een dunne compatibiliteitslaag. De implementatie is opgesplitst zodat metrics-verzameling, state-visualisatie en Dash-admin endpoints afzonderlijk testbaar zijn.

```mermaid
flowchart LR
    compatDashboard[dashboard_service.py]
    metricsCore[metrics_collector.py]
    visualizerCore[state_visualizer.py]
    adminCore[admin_endpoints.py]

    compatDashboard --> metricsCore
    compatDashboard --> visualizerCore
    compatDashboard --> adminCore
    visualizerCore --> metricsCore
    adminCore --> visualizerCore
    adminCore --> metricsCore
```

- `dashboard_service.py` bewaart de publieke en protected API als delegatie/proxy-laag.
- `metrics_collector.py` bevat performance-samenvattingen, heatmap-opbouw en blackboard health metingen.
- `state_visualizer.py` bevat figuur/panel-opbouw voor swarm, inference, parity, blackboard trend en drawdown.
- `admin_endpoints.py` bewaart een backward-compatible exportlaag.
- `admin_endpoints_core.py` bevat Dash-layout, callbacks en dashboard runtime-start.

### 3.4 State manager component

`lumina_core/state/state_manager.py` centraliseert de kritieke evolutie-state writes zodat JSONL en SQLite ook bij multi-process workloads consistent blijven.

```mermaid
flowchart LR
    writers[EngineAndEvolutionWriters]
    manager[state_manager.py]
    fileLocks[filelockLocks]
    jsonlStore[stateJsonlFiles]
    sqliteStore[stateSqliteFiles]

    writers --> manager
    manager --> fileLocks
    manager --> jsonlStore
    manager --> sqliteStore
```

- `safe_append_jsonl(...)` doet atomische append met lock, retry/backoff en optionele hash-chain (`prev_hash` + `entry_hash`).
- `safe_sqlite_connect(...)` forceert WAL + busy timeout voor veilige concurrente writes.
- `safe_with_file_lock(...)` ondersteunt geavanceerde write-transacties (zoals decision-log hash herberekening binnen dezelfde lock scope).
- Lockbestanden staan onder `state/.locks/` (of `LUMINA_STATE_LOCK_DIR`) en worden niet gecommit.

---

## 4. Event Bus & Blackboard Flow

Een typische **trade decision** loopt eerst door **constitutionele** en **shadow**-logica waar van toepassing; daarna wordt status en context **gepubliceerd** zodat subscribers (risk, evolution, blackboard) kunnen reageren zonder alles synchroon aan elkaar te koppelen.

```mermaid
sequenceDiagram
    participant Agent as DecisionSource
    participant Guard as ConstitutionalGuard
    participant Shadow as ShadowDeployment
    participant Bus as EventBus
    participant Risk as RiskContext
    participant Evo as EvolutionContext
    participant BB as Blackboard

    Agent->>Guard: evaluate principles pre-trade
    alt fatal violation
        Guard-->>Agent: block fail-closed
    else pass or warn path
        Guard->>Shadow: shadow eligibility check
        Shadow-->>Guard: verdict pending pass fail
        Guard->>Bus: publish trade decision event
        Bus->>Risk: notify subscribers
        Bus->>Evo: notify subscribers
        Bus->>BB: update shared state topics
        Risk-->>Agent: sizing gates feedback
    end
```

> Dit diagram is **conceptueel**: exacte methodenamen en topics staan in code ([`event_bus.py`](../lumina_core/agent_orchestration/event_bus.py), [`engine_bindings.py`](../lumina_core/agent_orchestration/engine_bindings.py)).

### 4.1 Event Bus payload contracts

Om schema-drift te beperken gebruikt de centrale Event Bus typed payload-contracten op geselecteerde kritieke topics. Validatie gebeurt fail-closed op publish-pad voor deze topics.

**Typed topics (Pydantic contracten):**
- `trading_engine.trade_signal.emitted` -> `TradeSignal`
- `trading_engine.dream_state.updated` -> `TradeSignal`
- `risk.policy.decision` -> `RiskDecision`
- `evolution.proposal.created` -> `EvolutionProposal`
- `evolution.shadow.verdict` -> `ShadowVerdict`
- `safety.constitution.violation` -> `ConstitutionViolation`
- `meta.agent.reflection` -> `AgentReflection`

**Legacy topics (nog zonder hard contract):**
- Niet-geregistreerde topics blijven legacy dict-payloads accepteren via `EventBus.publish(...)`.
- Dit houdt migraties backward-compatible voor bestaande producers en subscribers.

**Migratieregel:**
- Nieuwe safety-, risk- of execution-kritieke topics krijgen direct een Pydantic payload-contract in `event_bus.py`.
- `publish_validated(...)` blijft het fail-closed compatibiliteitspad voor topic-gebaseerde validatie.

---

## 5. Data Flow Example — Volledige trade cyclus

Van tick tot order: **data in**, **checks**, **leren observeren**, **risico**, **uitvoering**.

```mermaid
flowchart TD
    md[MarketData]
    eng[TradingEngine]
    const[ConstitutionCheck]
    sh[ShadowGate]
    evo[EvolutionMetaBlackboard]
    risk[RiskController]
    ex[ExecutionBroker]

    md --> eng
    eng --> const
    const -->|"fail"| stop([Stop flow])
    const -->|"pass"| sh
    sh -->|"block promotion"| stop
    sh --> evo
    evo --> risk
    risk --> ex
```

**Interpretatie:** als een stap **faalt**, gaat het organisme **fail-closed** — liever geen trade dan een ongeteste promotie of een risico dat de Noordster schendt.

### 5.1 Final order arbitration

Voor orderuitvoering gebruikt Lumina nu een expliciete **laatste gate**:

- `RiskPolicy.get_effective_policy(mode, instrument)` is de centrale resolver voor risk-limieten.
- Overlay-volgorde is nu strikt: `base (risk_controller) -> mode_overlay (sim/real/paper/sim_real_guard) -> instrument_overlay (risk_instrument_overrides)`.
- Voor config hot-reload zonder procesrestart wordt `ConfigLoader.invalidate()` gebruikt vóór de volgende policy-resolutie.
- `FinalArbitration` valideert elke orderintentie op constitution + risk policy + live account state.
- Deze check draait vóór broker submit in zowel engine- als brokerpaden, zodat geen agent-route de risicogrens kan omzeilen.

---

## 6. Technische Principes

- **Fail-closed design** — Onzekerheid, exceptions of ontbrekende checks leiden tot **blokkeren** en audit, niet tot stille acceptatie (zie ook [AGI_SAFETY.md](AGI_SAFETY.md)).
- **Event-driven communicatie** — Domeinen publiceren en subscriben via [`EventBus` / `DomainEvent`](../lumina_core/agent_orchestration/event_bus.py); zo blijven grenzen scherp en uitbreidingen testbaar.
- **Dependency Injection via ApplicationContainer** — [`ApplicationContainer`](../lumina_core/container.py) is het bootstrap-object: services en wiring zijn expliciet i.p.v. verborgen global state.
- **ADR-gedreven ontwikkeling** — Belangrijke keuzes staan in [`docs/adr/`](adr/README.md); wijzigingen aan grenzen of contracts gaan samen met een ADR.

---

## 7. Links

### Documentatie

- **ADR-index:** [docs/adr/README.md](adr/README.md)
- **AGI Safety (drie lagen):** [docs/AGI_SAFETY.md](AGI_SAFETY.md)

### Belangrijkste modules in `lumina_core/`

| Module / gebied | Pad |
|-----------------|-----|
| DI bootstrap | [`lumina_core/container.py`](../lumina_core/container.py) |
| Event Bus | [`lumina_core/agent_orchestration/event_bus.py`](../lumina_core/agent_orchestration/event_bus.py) |
| Blackboard | [`lumina_core/engine/agent_blackboard.py`](../lumina_core/engine/agent_blackboard.py) |
| Engine bindings | [`lumina_core/agent_orchestration/engine_bindings.py`](../lumina_core/agent_orchestration/engine_bindings.py) |
| Trading context | [`lumina_core/trading_engine/`](../lumina_core/trading_engine/) |
| Centrale engine | [`lumina_core/engine/lumina_engine.py`](../lumina_core/engine/lumina_engine.py) |
| Risk | [`lumina_core/risk/`](../lumina_core/risk/) |
| Evolution | [`lumina_core/evolution/`](../lumina_core/evolution/) |
| Evolution orchestrator (compat) | [`lumina_core/evolution/orchestrator.py`](../lumina_core/evolution/orchestrator.py) |
| Evolution orchestrator core | [`lumina_core/evolution/orchestrator_core.py`](../lumina_core/evolution/orchestrator_core.py) |
| Evolution fitness evaluator | [`lumina_core/evolution/fitness_evaluator.py`](../lumina_core/evolution/fitness_evaluator.py) |
| Evolution mutation pipeline | [`lumina_core/evolution/mutation_pipeline.py`](../lumina_core/evolution/mutation_pipeline.py) |
| Evolution promotion policy | [`lumina_core/evolution/promotion_policy.py`](../lumina_core/evolution/promotion_policy.py) |
| Self-evolution meta agent (compat) | [`lumina_core/engine/meta_agent.py`](../lumina_core/engine/meta_agent.py) |
| Self-evolution meta agent core | [`lumina_core/engine/meta_agent_core.py`](../lumina_core/engine/meta_agent_core.py) |
| Self-evolution proposal generator | [`lumina_core/engine/proposal_generator.py`](../lumina_core/engine/proposal_generator.py) |
| Self-evolution anomaly detector | [`lumina_core/engine/anomaly_detector.py`](../lumina_core/engine/anomaly_detector.py) |
| Self-evolution audit writer | [`lumina_core/engine/audit_writer.py`](../lumina_core/engine/audit_writer.py) |
| Dashboard service (split) | [`lumina_core/engine/dashboard_service.py`](../lumina_core/engine/dashboard_service.py) |
| Dashboard metrics collector | [`lumina_core/engine/metrics_collector.py`](../lumina_core/engine/metrics_collector.py) |
| Dashboard state visualizer | [`lumina_core/engine/state_visualizer.py`](../lumina_core/engine/state_visualizer.py) |
| Dashboard admin endpoints (compat) | [`lumina_core/engine/admin_endpoints.py`](../lumina_core/engine/admin_endpoints.py) |
| Dashboard admin endpoints core | [`lumina_core/engine/admin_endpoints_core.py`](../lumina_core/engine/admin_endpoints_core.py) |
| State manager | [`lumina_core/state/state_manager.py`](../lumina_core/state/state_manager.py) |
| Safety | [`lumina_core/safety/`](../lumina_core/safety/) |

### Cost model calibration en reality gap

LUMINA kalibreert execution-cost aannames dagelijks op basis van gereconcilieerde fills. Zo blijven risk-inschattingen aligned met live marktfrictie in plaats van statisch op paper-aannames.

```mermaid
flowchart LR
    reconcilerAudit[trade_fill_audit.jsonl]
    calibrator[CostModelCalibrator]
    calibrationState[state/cost_model_calibration.json]
    tradeCostModel[TradeExecutionCostModel]
    gapTracker[RealityGapTracker]
    gapLog[logs/reality_gap.jsonl]

    reconcilerAudit --> calibrator
    calibrator --> calibrationState
    calibrationState --> tradeCostModel
    reconcilerAudit --> gapTracker
    gapTracker --> gapLog
```

- [`lumina_core/risk/cost_model_calibrator.py`](../lumina_core/risk/cost_model_calibrator.py) vergelijkt per `reconciled` event `model_cost` versus `real_fill_cost` en schrijft running bias-statistiek naar `state/cost_model_calibration.json`.
- [`lumina_core/risk/cost_model.py`](../lumina_core/risk/cost_model.py) past de bias toe via `apply_calibration()` (ticks-bias + optionele sigma-update).
- [`lumina_core/monitoring/reality_gap_tracker.py`](../lumina_core/monitoring/reality_gap_tracker.py) meet dagelijks de gap tussen live fills en baseline-metrics, en appendt records naar `logs/reality_gap.jsonl`.
- [`scripts/validation/run_cost_model_calibration.py`](../scripts/validation/run_cost_model_calibration.py) is de dagelijkse validation-entrypoint voor beide stappen.

**V1-beperkingen (expliciet):**
- Reconciler-audit bevat nog geen ATR-snapshot of directe `model_cost`; de calibrator gebruikt daarom een expliciete ATR-fallback.
- De kostenvergelijking is een conservatieve exit-leg proxy (slippage + commissie) en geen volledige trade-TCA.

---

*LUMINA v5 — gebouwd voor **extreme intellectual honesty**, **rigoureuze testing** en **radicale creativiteit** binnen harde veiligheidsgrenzen.*
