---
name: pydantic-model
description: >
  Genereert strikte, hoogwaardige Pydantic v2 modellen volgens de LUMINA standaarden
  (extra=forbid, sterke Field constraints, validators, documentatie en type safety).
  Gebruik bij nieuwe Event Bus contracten, TradeSignal, RiskDecision, ConstitutionViolation,
  of wanneer de gebruiker Pydantic modellen aanmaakt.
---

# Pydantic Model Skill (v2.0)

**Doel**: Genereer perfecte, strikte Pydantic v2 modellen die voldoen aan de LUMINA kwaliteitseisen.

**Primaire bron**: `project-dna/lumina/AGENTS.md` + `event-bus-contract` skill

**Wanneer gebruiken**: Altijd wanneer een nieuw Pydantic model nodig is (vooral voor Event Bus payloads).

---

## Slimme Logica

**1. Auto-detect context**
- **Event payloads** (TradeSignal, RiskDecision, ConstitutionViolation, etc.) → zeer streng (`extra=forbid` + veel `Field` constraints)
- **Risk / Config modellen** → extra validatie met `model_validator`
- **Interne agent modellen** → streng maar iets flexibeler

**2. Auto-suggest Field constraints**
- `confidence`: `ge=0.0, le=1.0`
- `symbol`: `min_length=1, max_length=20`
- `quantity / price`: `gt=0`
- `severity`: `Literal["low", "medium", "high", "critical"]`

**3. Standaard regels**
- Nooit `Optional` gebruiken zonder `| None`
- Altijd `model_config = {"extra": "forbid"}` gebruiken
- Overweeg `strict=True` bij security- of risk-gerelateerde modellen
- Gebruik `UUID` type wanneer een id een UUID is

---

## Standaard Template

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, model_validator

class TradeSignal(BaseModel):
    """Contract for trade signals published on the Event Bus."""

    id: UUID = Field(default_factory=uuid4)
    symbol: str = Field(min_length=1, max_length=20)
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    source_agent: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
```

---

*Versie 2.0 — Verbeterde integratie met event-bus-contract en centrale AGENTS.md (juni 2026)*