# Architecture

Lumina is een zelflerend, zelf-evoluerend trading-organisme. De architectuur is expliciet ontworpen rond drie pijlers: **Safety First**, **Self-Evolving** en **Intellectual Honesty**.

## 1. High-Level Laagindeling

De architectuur is top-down opgebouwd:

1. **Safety Layer** (niet-breekbaar)
   - Trading Constitution (15 machine-enforced principes)
   - ConstitutionalGuard
   - Sandboxed execution + shadow deployment

2. **Evolution Layer**
   - DNA-mutatie, fitness-evaluatie, promotiebeleid
   - Parallel realities / meta-agents
   - Sterk beperkt in REAL mode

3. **Trading Engine + Agent Orchestration**
   - Bounded contexts
   - Centrale Event Bus (typed)
   - Blackboard voor agent-coördinatie

4. **Risk + Execution Layer** (laatste poort naar de markt)
   - Admission Chain
   - Risk Controller + Gates
   - Final Arbitration
   - Order Gatekeeper

Veiligheid en observability gaan vóór evolutie. Risk en execution zijn de laatste, strengste poorten.

## 2. Belangrijkste Bounded Contexts

Lumina gebruikt expliciete **bounded contexts** onder `lumina_core/` (zie ADR 0001).

| Context                  | Verantwoordelijkheid                                      | Belangrijkste modules                          | Opmerkingen |
|--------------------------|-----------------------------------------------------------|------------------------------------------------|-------------|
| **Safety**               | Constitutionele principes, sandboxing, promotiegates     | `safety/trading_constitution.py`, `constitutional_guard.py` | Fail-closed, mode-aware (REAL strengst) |
| **Evolution**            | Mutatie, fitness, shadow runs, promotiebeslissingen      | `evolution/` (orchestrator, mutation, promotion) | Agressief in SIM, zeer beperkt in REAL |
| **Risk Management**      | Pre-trade gates, position sizing, drawdown control       | `risk/` (admission_chain, risk_controller, final_arbitration, dynamic_kelly) | Kern van kapitaalbehoud |
| **Agent Orchestration**  | Event Bus, Blackboard, meta-agent coördinatie            | `agent_orchestration/event_bus.py`, blackboard | Primaire cross-context communicatie |
| **Trading Engine**       | Marktdata, strategie, operaties, valuation               | `engine/`, `trading_engine/`                   | Bevat nog legacy compat-laag |

## 3. Belangrijke Architectuurpatronen

### 3.1 Centrale Typed Event Bus
- Locatie: `lumina_core/agent_orchestration/event_bus.py`
- Alle domein-overstijgende communicatie loopt via gepubliceerde events.
- Gebruik van Pydantic-modellen (`publish_validated` + `payload_model`).
- Kritieke topics (RiskVerdict, FinalArbitrationResult, TradeIntent, ConstitutionViolation, etc.) hebben `extra="forbid"`.
- Tier A (strict) vs Tier B (flexibel) contracten.

### 3.2 Admission Chain + Final Arbitration
- `lumina_core/risk/admission_chain.py`
- Expliciete, traceerbare stappen: `session_equity_sync → risk_policy → final_arbitration → constitution → audit_write`
- Produceert een `AdmissionTrace` met per-stap resultaat.
- `final_arbitration.py` is de laatste constitutionele + risk check voordat een orderintent naar execution gaat.

### 3.3 Trading Constitution + ConstitutionalGuard
- 15 onveranderlijke principes in `safety/trading_constitution.py` (kapitaalbehoud, geen naked orders, kelly-cap, etc.).
- `ConstitutionalGuard` dwingt drie fasen af:
  1. `check_pre_mutation`
  2. Sandboxed evaluatie
  3. `check_pre_promotion`
- Alles fail-closed.

### 3.4 Shadow Deployment + Human Approval
- Radicale mutaties mogen nooit direct REAL orders plaatsen.
- Shadow-runs + expliciete human approval vereist bij bepaalde fitness-sprongen of risk flags (zie ADR 0002).

### 3.5 Fail-Closed Design
- Bij twijfel = reject.
- Brede except-blokken in kritieke paden zijn verboden of expliciet gelogd als fault.
- REAL mode heeft bijna altijd strengere regels dan SIM/Paper.

## 4. Hoe de lagen met elkaar communiceren

- **Intra-context**: directe calls binnen een bounded context.
- **Inter-context**: bij voorkeur via de **Event Bus** (gepubliceerde domain events).
- **Naar de markt**: uitsluitend via de **Admission Chain + Order Gatekeeper**.
  - Geen enkele agent of evolutie-component kan direct een order plaatsen.
- **Safety veto**: Safety layer kan evolutie en trading beslissingen vetoën via de Constitution en de Admission Chain.
- **Observability**: vrijwel alle belangrijke beslissingen (risk verdicts, constitution violations, promotion decisions) worden als typed events gepubliceerd.

## 5. Grootste Evolutionaire Knelpunten (huidige stand)

1. **Legacy compat-laag in de engine**
   - Veel oude modules (`lumina_engine.py`, `self_evolution_meta_agent.py`, etc.) zijn dunne delegatie-lagen naar nieuwe bounded context implementaties. Dit vertraagt het opruimen van god-class gedrag en cross-imports.

2. **Risk-laag is krachtig maar complex**
   - Zware mixin-structuur (`RiskGatesMixin`, `RiskAllocatorMixin`, etc.) in de risk controller maakt het moeilijk om kleine, gerichte evolutie-stappen te doen zonder veel context te moeten begrijpen.

3. **Event Bus contract maturity is nog incompleet**
   - Hoewel het mechanisme sterk is, zijn nog niet alle belangrijke risico- en evolutie-beslissingen volledig getypt en gepubliceerd op de bus (bijv. volledige `RiskVerdict` coverage was lange tijd afwezig).

4. **Meta-evolutie van de DNA zelf is nog jong**
   - Het Recursive Self-Improvement Protocol bestaat pas sinds kort. Er is nog weinig ervaring met het gecontroleerd evolueren van principes, anti-patterns en architectuurdocumentatie zelf.

5. **SIM vs REAL gedragsscheiding is deels impliciet**
   - Hoewel de constitution en admission chain mode-aware zijn, zijn er nog plekken waar de scheiding tussen "radicaal leren" en "kapitaal beschermen" niet expliciet genoeg in de code zit.

## 6. Principes die de architectuur moeten bewaken

- Risk logic moet altijd **zichtbaar en geïsoleerd** blijven.
- Geen god-files: componenten moeten klein en testbaar blijven.
- Nieuwe functionaliteit in evolution of agents mag nooit de Safety of Risk laag verzwakken.
- Alle belangrijke beslissingen moeten traceerbaar zijn via events of audit logs.

---

Deze architectuurbeschrijving is de huidige (2026) snapshot. Wijzigingen hierin volgen het **Recursive Self-Improvement Protocol**.