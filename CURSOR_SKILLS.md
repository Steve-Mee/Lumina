# LUMINA Cursor Skills — Overzicht & Gebruik

Dit document beschrijft alle skills die beschikbaar zijn in het LUMINA project en hoe je ze optimaal gebruikt.

---

## Overzicht van alle Skills

| Skill                    | Versie | Doel | Wanneer gebruiken |
|--------------------------|--------|------|-------------------|
| `token-efficiency`       | v1.1   | Forceert token-efficiënte workflow (Plan Mode, todo, juiste model-keuze, PR-splitting) | Altijd (automatisch) |
| `risk-safety-review`     | v1.1   | Reviewt code op kapitaalbehoud + geeft veiligheidsscore + concrete verbeterpunten | Bij elke risk/trading/constitution change |
| `pydantic-model`         | v1.1   | Genereert perfecte Pydantic v2 modellen met slimme context-detectie | Bij elk nieuw Pydantic model |
| `test-scaffolding`       | v1.1   | Genereert tests met juiste markers + fixtures | Bij elke nieuwe functionaliteit |
| `constitution-guard`     | v1.1   | Zorgt dat changes niet in strijd zijn met de Trading Constitution | Bij grotere wijzigingen |
| `adr-writer`             | v1.1   | Schrijft Architecture Decision Records + beslist automatisch of ADR nodig is | Bij architectuurwijzigingen |
| `event-bus-contract`     | v1.1   | Zorgt dat events via typed Pydantic contracts gaan | Bij Event Bus wijzigingen |

---

## Hoe activeer je de skills?

1. Zorg dat de map `.cursor/skills/` in je project root staat met alle `.md` bestanden.
2. Herlaad Cursor (`Ctrl + Shift + P` → **Reload Window**).
3. Ga naar **Settings → Skills** en zet alle skills **aan**.

---

## Hoe gebruik je de skills?

### Automatisch (aanbevolen)

Zodra de skills geactiveerd zijn, past de agent ze **automatisch** toe bij elke prompt. Je hoeft niets speciaals te doen.

### Handmatig aanroepen

Je kunt een skill altijd expliciet aanroepen met:

```bash
/token-efficiency
/risk-safety-review
/pydantic-model
/test-scaffolding
/constitution-guard
/adr-writer
/event-bus-contract
```

---

## Universeel Prompt Template (kopieer dit)

Gebruik dit template bij **elke** prompt:

```markdown
Je werkt strikt volgens de LUMINA .cursorrules (v5.1) en de missie.
Gebruik de token-efficiency skill + alle andere actieve skills.

**Taak:**
[paste hier je volledige taak]

**Extra eisen:**
- Werk atomic en token-efficiënt
- Gebruik Plan Mode + todo_write bij Complex of Safety-Critical taken
- Na elke sub-taak: ruff + mypy --strict + pyright + relevante tests
- Rapporteer aan het einde geschat vs werkelijk token-verbruik
```

---

## Belangrijke Gedragsregels

- **Nieuwe chat = nieuwe bounded context** — start een verse chat voor elke nieuwe module/laag.
- **Start bijna altijd in normale Composer** (niet Agent, niet Plan). De skill schakelt automatisch om als nodig.
- **Bij grote refactors (>1200 regels)**: de agent splitst automatisch in 2 PR’s (Core Split + Docs & Validatie) en geeft twee kant-en-klare prompts.
- **Safety-Critical taken**: de agent vraagt expliciet om bevestiging voordat hij premium model gebruikt.

---

## Aanbevolen mapstructuur

```
NinjatraderAI_Bot/
├── .cursorrules
├── CURSOR_SKILLS.md                 ← Dit bestand
├── .cursor/
│   └── skills/
│       ├── token-efficiency.md
│       ├── risk-safety-review.md
│       ├── pydantic-model.md
│       ├── test-scaffolding.md
│       ├── constitution-guard.md
│       ├── adr-writer.md
│       └── event-bus-contract.md
├── lumina_core/
├── tests/
├── docs/
│   └── architecture.md
└── config/
```

---

## Versiegeschiedenis

- **v1.1 (2 mei 2026)**: Alle skills uitgebreid met slimme logica (auto-detect context, auto-score, auto-marker, PR-splitting, etc.)
- **v1.0 (2 mei 2026)**: Initiële set van 7 skills

---

*Gemaakt voor LUMINA — 2 mei 2026*
