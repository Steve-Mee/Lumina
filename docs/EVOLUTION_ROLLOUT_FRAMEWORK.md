# Evolution Rollout Framework

> Kapitaalbehoud is heilig.  
> Nieuwe mutaties mogen nooit direct live orders plaatsen.

Deze rollout-laag maakt promotie van gemuteerde DNA-candidates expliciet
veilig en auditeerbaar.

## Doel

- Shadow-first validatie voor REAL promoties.
- Verplichte human approval bij radicale mutaties.
- A/B context opnemen in promotiebeslissing.
- Volledige audit trail voor elke rollout-decision.

## Componenten

- `lumina_core/evolution/rollout.py`
  - `EvolutionRolloutFramework`
  - `RolloutDecision`
- `lumina_core/evolution/evolution_orchestrator.py`
  - gebruikt rollout-framework als laatste safety gate voor promotie
- `lumina_core/evolution/evolution_dashboard.py`
  - toont rollout-beslissingen in "Rollout Safety Gate"

## Beslislogica

1. **Shadow deployment (REAL)**
   - REAL promotie vereist afgeronde shadow-validatie (`shadow_passed=True`).
   - Tijdens shadow-run worden alleen hypothetische fills gebruikt.
2. **Radicale mutaties**
   - Detectie op basis van fitness-sprong en/of risk flags.
   - In REAL/PAPER is expliciete human approval verplicht.
3. **A/B context**
   - Vergelijkt geselecteerde variant-score met gemiddelde van alle varianten.
   - Uitkomst wordt geaudit (`ab_verdict`).
4. **Fail-closed promotie**
   - Als shadow of human-approval gate faalt, geen promotie.

## Audit en observability

- Rollout-auditlog:
  - `state/evolution_rollout_history.jsonl`
  - event: `rollout_decision`
  - velden: stage, reason, human approval flags, radical mutatie, A/B verdict
- Metrics-event:
  - `generation_completed` bevat rolloutvelden in `logs/evolution_metrics.jsonl`

## Zero-risk live trading policy

- Nieuwe mutaties draaien in shadow-context voordat REAL promotie kan.
- `live_orders_blocked` staat altijd aan in rollout-beslissingen.
- Radicale wijzigingen zonder expliciete menselijke goedkeuring worden geblokkeerd.

## Tests

- `tests/test_evolution_rollout.py`
  - shadow-required gedrag in REAL
  - human-approval gate bij radicale mutaties
  - happy path promotie
  - auditlog persistency
- `tests/test_evolution_dashboard.py`
  - rollout-history loader
  - dashboardsectie "Rollout Safety Gate"
