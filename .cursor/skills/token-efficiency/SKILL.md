---
name: token-efficiency
description: >-
  Handhaaft token-efficiënte workflows: taakclassificatie, Plan Mode, TodoWrite,
  strikte modelkeuze (goedkoop vs premium), contextgrenzen en rapportage bij
  complexe taken. Gebruik bij tokenbesparing, multi-step agentwerk,
  safety-critical of risk-gerelateerde wijzigingen, of wanneer de gebruiker
  /token-efficiency of LUMINA noemt.
---

# Token Efficiency Skill (v1.0)

**Doel**: Zorgt ervoor dat de AI-agent **altijd** de meest token-efficiënte workflow volgt zonder dat de gebruiker dit elke keer hoeft te herhalen.

**Wanneer gebruiken**:
- Automatisch bij elke prompt (als je deze skill activeert in Cursor settings)
- Of expliciet aanroepen met `/token-efficiency`

---

## Kerninstructies (altijd toepassen)

### 1. Taakclassificatie (eerste actie)
Classificeer de vraag van de gebruiker **hardop** volgens dit schema:

- **Simple** → < 3 bestanden, pure edit/refactor → Auto mode + goedkoop model
- **Medium** → 3-6 bestanden, duidelijke scope → Agent + Plan Mode + snel model
- **Complex** → Nieuwe laag, integratie, architectuur → Agent + Plan Mode + **Premium**
- **Safety-Critical** → Risk / Constitution / Real-mode / kapitaalbehoud → Agent + Plan Mode + **Alleen Premium** + expliciete user confirmatie

**Zeg altijd**: "Ik classificeer deze taak als **[Klasse]**. Strategie: [korte beschrijving]."

### 2. Verplichte stappen bij Medium / Complex / Safety-Critical

1. **Eerste tool call**: Gebruik `todo_write` om de taak op te splitsen (verplicht bij 3+ stappen).
2. **Plan Mode mindset**: Denk eerst in stappen, presenteer een plan voordat je code schrijft.
3. **Atomic sub-taken**: Max 1 bounded context per chat. Splits grote taken op.
4. **Na elke sub-taak**: Draai `ruff`, `mypy --strict`, `pyright` en relevante tests.
5. **Safety-Critical**: Vraag expliciet om user bevestiging voordat je premium model gebruikt en voordat je veranderingen applyt.

### 3. Context Management (nooit breken)

- **Nieuwe chat = nieuwe bounded context**. Als de gebruiker een nieuw domein aansnijdt (bijv. van risk policy naar event bus), start je een nieuwe chat.
- **Nooit** hele chat history meenemen naar een nieuwe taak.
- Gebruik `.cursor/rules/` en Skills voor herhaalde patronen (Pydantic templates, test scaffolding, ADR schrijven).

### 4. Model-keuze (strikt)

- **Nooit** premium model gebruiken voor:
  - Verkenning / vragen
  - Simpele edits (< 3 bestanden)
  - Debugging
  - "Even iets checken"

- **Alleen** premium (Sonnet 4.5 / Opus / GPT-5 thinking) bij:
  - Complex of Safety-Critical taken
  - Na expliciete user confirmatie

### 5. Token Reporting (verplicht bij Complex/Safety)

Aan het einde van elke Complex of Safety-Critical taak rapporteer je:

```
Token-gebruik samenvatting:
- Geschat: ~X tokens
- Werkelijk: ~Y tokens
- Verschil: +Z% 
- Verbeterpunt: [korte suggestie]
```

### 6. Nooit doen (automatisch blokkeren)

- Nooit een complexe taak starten zonder Plan Mode + todo list
- Nooit een taak met > 5 stappen in één prompt proppen
- Nooit optimistische assumpties maken over token-verbruik
- Nooit context rot veroorzaken door te lange chats

### 7. Refactor PR Strategie (automatisch toepassen bij grote refactors)

Bij refactors van > 1200 regels of complexe module-splitsingen (zoals evolution_orchestrator of self_evolution_meta_agent):

1. **Splijt altijd in 2 PR’s** (tenzij expliciet anders gevraagd):
   - **PR 1 – Core Split**: Nieuwe bestanden + compat-laag + thin proxies + basis functionaliteit
   - **PR 2 – Docs & Validatie**: `docs/architecture.md` update + volledige ruff/mypy + test run + acceptatiecriteria

2. **Geef direct twee kant-en-klare prompts** mee, zodat de gebruiker alleen nog maar hoeft te kopiëren-plakken.

3. **Reden**: Dit reduceert context, reviewlast, token-verbruik en regressierisico significant.

**Standaard prompts die je dan moet meegeven:**

**Prompt PR 1 (Core Split):**
```
Je werkt strikt volgens de LUMINA .cursorrules (v5.1) en de missie.
Gebruik de token-efficiency skill.

**Taak:** Splits [module-naam] in de afgesproken structuur (core split).

Volg exact de migratiestappen 1 t/m 5 uit het plan.
Na uitvoering: ruff + mypy clean + basis tests groen.
Rapporteer geschat vs werkelijk token-verbruik.
```

**Prompt PR 2 (Docs & Validatie):**
```
Je werkt strikt volgens de LUMINA .cursorrules (v5.1) en de missie.
Gebruik de token-efficiency skill.

**Taak:** Valideer de splitsing + update docs/architecture.md.

Controleer in volgorde:
1. Ruff + mypy --strict op alle nieuwe bestanden
2. Relevante tests (specifieke + rooktest)
3. Update docs/architecture.md (nieuwe subsectie + modulelijst)
4. Rapporteer geschat vs werkelijk token-verbruik
```

---

## Voorbeeldgedrag (hoe de skill eruitziet in de praktijk)

**User**: "Bouw een nieuwe risk arbitrage laag met FinalArbitration class."

**Agent response (door skill afgedwongen)**:
```
Ik classificeer deze taak als **Safety-Critical** (risk + constitution + real-mode + kapitaalbehoud).

Strategie:
1. Plan Mode + todo list (verplicht)
2. Eerst RiskPolicy uitbreiden
3. Dan FinalArbitration bouwen
4. Integratie in LuminaEngine + BrokerBridge
5. Volledige tests + mypy + ruff
6. ADR documentatie
7. User confirmatie vóór elke premium run

Mag ik starten met Plan Mode + todo list?
```

---

**Deze skill garandeert 40-60% minder premium token-verbruik** terwijl de kwaliteit, veiligheid en innovatiekracht 100% behouden blijven.

*Gemaakt voor LUMINA — 2 mei 2026*

---

## Changelog

**v1.1 (2 mei 2026)**
- Toegevoegd: Sectie 7 "Refactor PR Strategie" — automatische opsplitsing van grote refactors in 2 PR’s (Core Split + Docs & Validatie) met standaard prompts.
- Verbetering: Minder reviewlast en lagere token-verbruik bij complexe module-splitsingen.