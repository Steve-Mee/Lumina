---
name: event-bus-contract
description: >
  Handhaaft typed Pydantic contracten voor de Event Bus. Forceert het gebruik van
  payload_model bij publish, verbiedt raw dicts na migratie, en zorgt voor
  gevalideerde model instances bij subscribers.
---

# Event Bus Contract Skill (v2.0)

**Doel**: Zorgt dat alle events op de Event Bus via strikte typed Pydantic contracten gaan.

**Primaire bron**: `project-dna/lumina/AGENTS.md` + `pydantic-model` skill

**Wanneer gebruiken**: Bij elke wijziging aan de Event Bus, publishers of subscribers.

---

## Kernregels

1. **Nieuwe topics** krijgen altijd een Pydantic model (zie `pydantic-model` skill).
2. **Publish** moet gebeuren met `payload_model=SomeModel`.
3. **Backward compatibility** met raw dicts mag alleen tijdelijk (max 2 weken) en moet expliciet gedocumenteerd zijn.
4. **Subscribers** ontvangen altijd een gevalideerd Pydantic model instance (nooit een dict).
5. **Schema violations** moeten een `ConstitutionViolation` of `RiskDecision` triggeren.

---

## Slimme Logica

- Bij een nieuw topic → forceer direct een Pydantic model + `publish(..., payload_model=...)`.
- Bij gebruik van raw dicts → waarschuw + stel migratiepad voor.
- Werk altijd samen met `constitution-guard` bij kritieke topics (risk, orders, constitution).

---

## Voorbeeld Correct Gebruik

```python
event_bus.publish(
    "trade.signals",
    signal_data,
    payload_model=TradeSignal   # ← verplicht
)
```

**Verboden**:
```python
event_bus.publish("trade.signals", signal_data)  # ← raw dict → blokkeren
```

---

*Versie 2.0 — Sterkere koppeling met pydantic-model en constitution-guard (juni 2026)*