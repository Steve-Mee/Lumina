# ADR-0004: Purged Cross-Validation, Order Book Replay en Reality Gap Penalty

**Status:** Accepted  
**Date:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

Conventionele backtests overschatten vaak performance door leakage, simplistische executiemodellen en onvoldoende correctie voor sim-live afwijking. Dat creëert een vals gevoel van veiligheid bij rollout-beslissingen.

Deze keuze dient expliciet de LUMINA-missie: extreme intellectual honesty (geen optimistische aannames), rigoureuze testing (realistische validatieketen), radicale creativiteit (meervoudige realisme-correcties in het fitnessproces). Binnen het Elon Musk Mindset Protocol passen we first principles toe op marktrealisme: score alleen wat onder realistische frictie overeind blijft.

## Decision

We voeren een realisme-gedreven validatiestandaard in voor evolution en evaluatie:

- **Purged Cross-Validation:** voorkomt temporal leakage tussen train/validate vensters.
- **Order Book Replay:** simuleert execution met diepere marktmicrostructuur dan candle-only aannames.
- **Reality Gap Penalty:** corrigeert fitnessscore voor verwacht verschil tussen simulatie en live gedrag.
- Resultaten uit deze keten wegen zwaar in promotiebeslissingen en rollout-gating.

## Consequences

### Positive

- Significant lager risico op overfitting en sim-illusies.
- Betere voorspellende waarde van backtests voor echte uitvoeringsomstandigheden.
- Consistentere governance: alleen strategieën met robuuste realisme-score komen door.

### Negative

- Hogere compute- en implementatiekosten door rijkere simulatiemodellen.
- Potentieel lagere nominale backtest-scores door strengere penalties, wat korte-termijnoptimisme tempert.

## Alternatives considered

1. Klassieke k-fold zonder purging — verworpen door leakage-risico in tijdreeksen.
2. Candle-only execution model — verworpen wegens onderschatting van slippage/queue effects.
3. Geen reality-gap correctie — verworpen door historisch bekende sim-live mismatch.

## Links

- Gerelateerde ADRs: `docs/adr/0002-shadow-deployment-human-approval.md`, `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
- Gerelateerde code: `lumina_core/engine/backtest/cross_validation.py`, `lumina_core/engine/backtest/order_book.py`, `lumina_core/engine/backtest/reality_gap.py`
- Gerelateerde tests: `tests/test_evolution_rollout.py`, `tests/test_dashboard_drawdown_runtime_e2e.py`
