# ADR-0005: Test Suite Overhaul met Markers, Timeouts en Isolated Fixtures

**Status:** Proposed  
**Date:** 2026-05-01  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

Naarmate LUMINA sneller evolueert, groeit de kans op trage, instabiele of niet-deterministische tests die regressies maskeren en feedbackloops vertragen. Voor een zelf-lerend systeem is testdiscipline een architectuurkeuze, geen bijzaak.

Deze beslissing verankert de LUMINA-missie expliciet: extreme intellectual honesty (tests moeten waarheid tonen, niet alleen groen kleuren), rigoureuze testing (strikte isolatie en timeout-beleid), radicale creativiteit (sneller experimenteren dankzij betrouwbare feedback). Ze sluit aan op het Elon Musk Mindset Protocol via first principles: betrouwbare iteratiesnelheid bepaalt innovatiekracht.

## Decision

We standaardiseren de testsuite met drie verplichte pijlers:

- **Markers:** heldere testsegmentatie (`unit`, `integration`, `slow`, `nightly`) voor voorspelbare CI-routes.
- **Timeouts:** expliciete timeouts per risicoprofiel om hangende tests fail-closed af te handelen.
- **Isolated fixtures:** filesystem/state/network isolatie zodat tests deterministisch en parallel-safe blijven.
- Nieuwe functionaliteit moet marker-correcte tests toevoegen als kwaliteitsgate.

## Consequences

### Positive

- Snellere en betrouwbaardere regressiedetectie.
- Minder flaky runs door strikte isolatie van side effects.
- Beter schaalbare CI-strategie met gerichte suites per ontwikkelfase.

### Negative

- Initiële migratiekost voor bestaande tests die nog niet marker/fixture-conform zijn.
- Hogere discipline-eis voor contributors bij het ontwerpen van testbare componenten.

## Alternatives considered

1. Huidige tests ongewijzigd laten groeien — verworpen door oplopend flake- en onderhoudsrisico.
2. Alleen CI-timeouts zonder fixture-isolatie — verworpen; pakt root cause van nondeterminisme niet aan.
3. Volledig handmatige testselectie per release — verworpen wegens lage reproduceerbaarheid en hoge menselijke foutkans.

## Links

- Gerelateerde ADRs: `docs/adr/0001-bounded-contexts-central-event-bus.md`, `docs/adr/0004-backtest-realism-purged-cv-orderbook-replay-reality-gap.md`
- Gerelateerde config: `pytest.ini`, `pyproject.toml`
- Gerelateerde tests: `tests/test_bounded_context_imports.py`, `tests/test_event_bus.py`, `tests/test_risk_controller.py`
