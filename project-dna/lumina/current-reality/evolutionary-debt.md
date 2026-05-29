# Evolutionary Debt

Dit document catalogiseert de grootste knelpunten die de toekomstige evolueerbaarheid van Lumina momenteel beperken. Het is een levend document.

## Huidige Top Debt Items (2026-05)

1. **Monolithische LuminaEngine**
   - Verantwoordelijkheden over te veel domeinen (PnL, RL, backtesting, risk, dream state, etc.).
   - Maakt redeneren over grenzen en test-isolatie moeilijk.
   - Status: Gedeeltelijk opgesplitst, maar legacy compat-laag nog aanwezig.

2. **Legacy Compat Layers**
   - Dunne delegatie-lagen in engine/, risk/ en meta-agent lagen.
   - Vertraagt de transitie naar echte bounded contexts.
   - Verhoogt regressierisico bij refactors.

3. **Risk Layer Complexiteit**
   - Zware mixin-structuur (`RiskGatesMixin`, etc.).
   - Moeilijk om kleine, gerichte evolutie-stappen te doen zonder veel context.

4. **Event Bus Contract Maturity**
   - Niet alle belangrijke beslissingen (risk, evolutie, governance) zijn volledig getypt en gepubliceerd.
   - Beperkt de observability en meta-agent capaciteit.

5. **Meta-Evolutie van DNA zelf nog jong**
   - Het Recursive Self-Improvement Protocol en de feedback loops op de DNA-laag zijn recent geïntroduceerd.
   - Weinig ervaring met het daadwerkelijk meten van de effectiviteit van meta-verbeteringen.

6. **SIM vs REAL scheiding nog deels impliciet**
   - Hoewel constitution en admission chain mode-aware zijn, zijn er nog plekken waar de scheiding niet expliciet genoeg is geïmplementeerd.

## Hoe deze lijst wordt onderhouden

- Nieuwe debt items worden toegevoegd via het Recursive Self-Improvement Protocol.
- Items worden verwijderd of gedowngraded als er aantoonbare vooruitgang is geboekt.
- De lijst wordt minimaal elke 90 dagen geëvalueerd als onderdeel van de DNA review.

**Doel**: Deze lijst moet over tijd korter en minder kritiek worden, niet langer. Als hij groeit, faalt ons zelfverbeteringsproces.