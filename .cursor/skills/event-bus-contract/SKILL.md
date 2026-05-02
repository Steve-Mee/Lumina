---
name: event-bus-contract
description: >-
  Handhaaft typed Pydantic-contracten voor de Event Bus: geen raw dicts na migratie,
  verplicht payload_model bij publish, tijdelijke backward compatibility (max 2 weken,
  gedocumenteerd), subscribers ontvangen gevalideerde model instances, schema
  violations → ConstitutionViolation of RiskDecision. Gebruik bij wijzigingen aan
  Event Bus, publishers/subscribers, of wanneer de gebruiker event-bus-contract,
  typed events, of event publishing noemt.
---

# Event Bus Contract Skill (v1.1)

**Doel**: Zorgt dat alle events via typed Pydantic contracts gaan (geen raw dicts meer na migratie).

**Wanneer gebruiken**: Bij elke wijziging aan de Event Bus of publishers/subscribers.

---

## Slimme logica (automatisch toepassen)

**1. Auto-detect nieuw topic**
- Als er een nieuw topic wordt toegevoegd → forceer Pydantic model + Protocol.

**2. Auto-suggest publish patroon**
- Geeft direct het correcte `publish(..., payload_model=...)` voorbeeld.

**3. Auto-controle backward compat**
- Bij gebruik van raw dicts → waarschuw + stel migratiepad voor (max 2 weken).

---

**Regels**:

1. **Nieuwe topics** krijgen altijd een Pydantic model (zie `pydantic-model` skill)
2. **Publish** met `payload_model=SomeModel` is verplicht voor nieuwe topics
3. **Backward compatibility** mag alleen tijdelijk (max 2 weken) en moet expliciet gedocumenteerd zijn
4. **Subscribers** moeten altijd een gevalideerd model instance ontvangen (nooit dict)
5. **Schema violations** moeten een `ConstitutionViolation` of `RiskDecision` triggeren

**Voorbeeld correct gebruik**:
```python
event_bus.publish(
    "trade.signals",
    {"symbol": "AAPL", ...},
    payload_model=TradeSignal   # ← verplicht
)
```

**Verboden**:
```python
event_bus.publish("trade.signals", {"symbol": "AAPL", ...})  # ← raw dict → blokkeren
```