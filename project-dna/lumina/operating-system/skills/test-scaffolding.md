---
name: test-scaffolding
description: >-
  Genereert tests volgens LUMINA teststandaarden (pytest markers, fixtures,
  gegeven-wanneer-dan structuur, fail-closed paden, monkeypatch/mocker). Gebruik
  bij nieuwe functionaliteit of wijzigingen die getest moeten worden, bij test
  scaffolding, of wanneer de gebruiker test-scaffolding, pytest markers, of
  LUMINA tests noemt.
---

# Test Scaffolding Skill (v1.1)

**Doel**: Genereer tests die voldoen aan de LUMINA teststandaarden (markers, fixtures, gegeven-structuur, coverage).

**Wanneer gebruiken**: Bij elke nieuwe functionaliteit of wijziging die getest moet worden.

---

## Slimme logica (automatisch toepassen)

**1. Auto-detect test type**
- Pure functies / helpers → `@pytest.mark.unit`
- Meerdere modules + I/O / DB / API → `@pytest.mark.integration`
- > 2 seconden of zware setup → `@pytest.mark.slow`
- Nachtelijke / end-to-end flows → `@pytest.mark.nightly`

**2. Auto-generate fixtures**
- Als er een class getest wordt → genereer `def xxx(self)` fixture
- Als er externe dependencies zijn → voeg `monkeypatch` of `mocker` toe

**3. Auto-suggest test cases**
- Altijd "happy path" + "fail-closed" + "edge case" testen

---

**Standaard structuur**:
```python
import pytest
from lumina_core.risk.final_arbitration import FinalArbitration, OrderIntent

@pytest.mark.unit
class TestFinalArbitration:
    @pytest.fixture
    def arbitration(self):
        return FinalArbitration()

    def test_valid_order_approved(self, arbitration):
        # gegeven
        intent = OrderIntent(...)
        state = {...}

        # wanneer
        result = arbitration.check_order_intent(intent, state)

        # dan
        assert result.decision == ArbitrationDecision.APPROVED

    def test_risk_limit_overshoot_rejected(self, arbitration):
        # gegeven
        ...

        # wanneer
        result = ...

        # dan
        assert result.decision == ArbitrationDecision.REJECTED
```

**Extra regels**:
- Altijd "gegeven-wanneer-dan" structuur gebruiken
- Test expliciet de **fail-closed** paden
- Gebruik `monkeypatch` of `mocker` voor externe dependencies