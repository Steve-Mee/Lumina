---
name: risk-safety-review
description: >-
  Reviewt wijzigingen op LUMINA REAL-mode kapitaalbehoud: fail-closed, strengere REAL-limieten,
  geen optimistische aannames, ConstitutionViolation en logging. Gebruik bij risk, trading,
  order-flow, constitution, agents of real-mode; bij /risk-review of risk-safety-review.
---

# Risk Safety Review Skill (v1.1)

**Doel**: Review elke code change op naleving van de heilige LUMINA regel: **Kapitaalbehoud is heilig in REAL mode**.

**Wanneer gebruiken**: Bij **elke** wijziging die risk, trading, constitution of real-mode raakt (automatisch of via `/risk-review`).

---

## Slimme logica (automatisch toepassen)

1. **Auto-detect context**
   - Als de change `PromotionPolicy`, `RiskDecision`, `ConstitutionalGuard`, `shadow`, `veto` of `REAL` raakt → **hoge prioriteit** + extra checks.

2. **Auto-score (0-10)**
   - Geef een veiligheidsscore gebaseerd op:
     - Fail-closed aanwezig? (+3)
     - REAL mode limieten strenger? (+2)
     - ConstitutionViolation event? (+2)
     - Logging + agent_id? (+2)
     - Optimistische assumpties? (-3)

3. **Auto-suggest verbeteringen**
   - Als score < 7 → geef concrete suggesties (bijv. "Voeg `require_margin_buffer` toe in REAL mode").

---

## Standaard checklist (altijd controleren)

1. **Fail-closed design**
   - Is er een expliciete "reject" pad bij elke validatie?
   - Kan een order ooit "per ongeluk" goedgekeurd worden?

2. **REAL mode strengheid**
   - Zijn limieten in REAL mode lager dan in Paper/Sim?
   - Is er een extra `require_margin_buffer` of `require_constitution_check`?

3. **Geen optimistische assumpties**
   - Wordt er ergens aangenomen dat een prijs positief is, een agent trusted is, etc.?

4. **Constitution check**
   - Wordt `ConstitutionViolation` event gepubliceerd bij overtreding?
   - Is er een blokkade voor agents met recente violations?

5. **Token & logging**
   - Wordt elke reject gelogd met duidelijke reden?
   - Wordt de user/agent die de order voorstelde gelogd?

---

## Output formaat (verplicht)

```
Risk Safety Review (Score: 8/10)
✅ Fail-closed: Ja
✅ REAL mode stricter: Ja (daily_loss 0.8% vs 3%)
✅ ConstitutionViolation event: Ja
⚠️  Warning: Margin buffer check mist in BrokerBridge
✅ Logging + agent_id: Ja

Verbeterpunten:
- Voeg `require_margin_buffer: 1.5` toe in REAL mode (lijn 87)
- Overweeg extra test voor "reject zonder expliciete reden"

Conclusie: Change kan door, mits bovenstaande 2 punten worden opgelost.
```

**Regel**: Als er een score < 6 is → **blokkeer** de change en eis aanpassingen.