---
name: pydantic-model
description: >-
  Genereert strikte Pydantic v2-modellen volgens LUMINA (extra=forbid, Field-constraints,
  Literal-enums, validators, documentatie). Gebruik bij nieuwe contractmodellen
  (TradeSignal, RiskDecision, ConstitutionViolation, event payloads), bij @pydantic-model,
  of wanneer de gebruiker Pydantic-modellen, BaseModel, of schema’s voor de Event Bus noemt.
---

# Pydantic Model Skill (v1.1)

**Doel**: Genereer perfecte, strikte Pydantic v2 modellen die voldoen aan de LUMINA standaarden (extra=forbid, validators, type hints, documentatie).

**Wanneer gebruiken**: Altijd wanneer een nieuw Pydantic model nodig is (TradeSignal, RiskDecision, ConstitutionViolation, etc.).

---

## Slimme logica (automatisch toepassen)

**1. Auto-detect context**
- **Event** (TradeSignal, RiskDecision, ConstitutionViolation, ShadowVerdict, etc.) → streng + `extra=forbid` + veel `Field` constraints
- **Risk/Config** → extra validatie + `model_validator`
- **Agent/Internal** → iets flexibeler, maar nog steeds `extra=forbid`

**2. Auto-suggest Field constraints**
- `confidence` → `ge=0.0, le=1.0`
- `symbol` → `min_length=1, max_length=20`
- `quantity / price` → `gt=0`
- `severity` → `Literal["low", "medium", "high", "critical"]`

**3. Auto-add validators**
- Als er business rules zijn (bijv. `daily_loss_limit < max_open_risk`) → stel `model_validator` voor.

---

**Standaard template**:
```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field, model_validator

class TradeSignal(BaseModel):
    """Contract for trade signals published by agents."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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

**Extra regels**:
- Nooit `Optional` gebruiken zonder `| None`
- Altijd `strict=True` overwegen bij security-gerelateerde modellen
- Gebruik `UUID` type als id een UUID is