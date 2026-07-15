# Architecture (Current Reality)

*Deze inhoud is gemigreerd uit de vorige architecture.md als onderdeel van de DNA 2.0 redesign.*

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

(Volledige details uit vorige versie — zie evolution/log/ voor de context van de verdieping op 2026-05-30)

### 3.1 Centrale Typed Event Bus
- Locatie: `lumina_core/agent_orchestration/event_bus.py`
- Alle domein-overstijgende communicatie loopt via gepubliceerde events.
- Gebruik van Pydantic-modellen (`publish_validated` + `payload_model`).
- Kritieke topics hebben `extra="forbid"`.
- Tier A (strict) vs Tier B (flexibel) contracten.

### 3.2 Admission Chain + Final Arbitration
- Expliciete, traceerbare stappen.
- Produceert een `AdmissionTrace`.

### 3.3 Trading Constitution + ConstitutionalGuard
- 15 onveranderlijke principes.
- Drie-fasen fail-closed model.

### 3.4 Shadow Deployment + Approval Gates (incl. Approval Twin)
- Radicale mutaties nooit direct in REAL zonder gates (shadow + constitution + PromotionGate).
- **Approval Twin** (ADR-0031/0032) is de primary *judgment* signal for birth/SIM/autonomy when high-conf + clean — a user-trained human replacement layer, not a gate bypass.
- REAL remains multi-layer: Twin may recommend; sandbox, constitution, shadow aperture and PromotionGate still decide.
- Living detail: `docs/roadmap.md` §6.

### 3.5 Fail-Closed Design
- Bij twijfel = reject.

## 4. Hoe de lagen met elkaar communiceren

- **Intra-context**: directe calls.
- **Inter-context**: bij voorkeur via de **Event Bus**.
- **Naar de markt**: uitsluitend via de **Admission Chain + Order Gatekeeper**.
- **Safety veto**: via Constitution en Admission Chain.

## 5. Grootste Evolutionaire Knelpunten (huidige stand)

Zie `current-reality/evolutionary-debt.md` voor de bijgewerkte en prioritaire lijst.

## 6. Principes die de architectuur moeten bewaken

- Risk logic moet altijd **zichtbaar en geïsoleerd** blijven.
- Geen god-files.
- Nieuwe functionaliteit in evolution of agents mag nooit de Safety of Risk laag verzwakken.
- Alle belangrijke beslissingen moeten traceerbaar zijn via events of audit logs.

---

*Deze versie is gemigreerd tijdens de DNA 2.0 redesign (2026-05-29). Volledige historische context van de verdieping staat in evolution/log/2026-05-30-deepened-architecture.md.*