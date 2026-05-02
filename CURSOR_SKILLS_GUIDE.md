# Cursor Skills — Complete Handleiding voor LUMINA (2026)

## Wat zijn Cursor Skills?

**Skills** zijn herbruikbare instructies die de AI-agent automatisch of op commando kan gebruiken.  
Ze zorgen ervoor dat je **niet elke keer dezelfde regels hoeft te herhalen** (zoals token-efficiëntie, Pydantic standaarden, test patronen, etc.).

Voordelen:
- Minder tokens (minder herhaling in prompts)
- Consistente kwaliteit
- Snellere ontwikkeling
- Minder fouten

---

## Stap-voor-stap: Hoe voeg je de `token-efficiency` skill toe?

### Stap 1: Maak de juiste mapstructuur

In je LUMINA project root (waar je `.cursorrules` staat), maak je:

```bash
mkdir -p .cursor/skills
```

### Stap 2: Plaats de skill

Kopieer het bestand `token-efficiency.md` naar:

```
.cursor/skills/token-efficiency.md
```

### Stap 3: Activeer de skill in Cursor

**Optie A — Via Cursor Settings (aanbevolen):**

1. Open Cursor
2. Ga naar **Settings** (Ctrl + ,)
3. Zoek op "Skills"
4. Onder "Project Skills" zie je `token-efficiency`
5. Zet de toggle **aan**

**Optie B — Via commando in Composer:**

Typ in de Composer / Agent chat:

```
/enable-skill token-efficiency
```

### Stap 4: Test de skill

Typ in een nieuwe Composer chat:

```
/token-efficiency
```

Je zou nu direct een bericht moeten krijgen zoals:

> "Ik classificeer deze taak als **Safety-Critical**..."

---

## Hoe gebruik je de skill in de praktijk?

### Automatisch (beste manier)

Zodra de skill geactiveerd is, **past hij automatisch toe** bij elke prompt.  
Je hoeft niets speciaals te doen — de agent classificeert zelf en kiest de juiste strategie.

### Handmatig aanroepen

Als je even expliciet wilt:

```
/token-efficiency
```

Of gecombineerd met een taak:

```
/token-efficiency Bouw de nieuwe ConstitutionViolation handler
```

---

## Aanbevolen extra skills voor LUMINA

Hier zijn de skills die ik sterk aanraad voor jouw project:

| Skill                    | Doel                                                                 | Wanneer gebruiken                  | Token-besparing |
|--------------------------|----------------------------------------------------------------------|------------------------------------|-----------------|
| `token-efficiency`       | Altijd de juiste modus + model + workflow                            | Altijd                             | ★★★★★          |
| `pydantic-model`         | Genereer perfecte Pydantic v2 modellen met `extra=forbid`, validators | Bij elke nieuw model               | ★★★★           |
| `test-scaffolding`       | Maak tests met juiste markers (@unit, @integration, @slow)           | Bij elke nieuwe functionaliteit    | ★★★★           |
| `adr-writer`             | Schrijf Architecture Decision Records in correct formaat             | Bij belangrijke architectuurkeuzes | ★★★            |
| `risk-safety-review`     | Review code op kapitaalbehoud, fail-closed, constitution             | Bij alles wat risk raakt           | ★★★★★          |
| `event-bus-contract`     | Zorg dat events altijd via typed contracts gaan                      | Bij event bus wijzigingen          | ★★★★           |
| `ninja-trader-patterns`  | Specifieke patronen voor NinjaTrader (strategies, indicators, etc.)  | Bij NinjaTrader integratie         | ★★★            |
| `constitution-guard`     | Check of changes niet in strijd zijn met Trading Constitution        | Bij elke grotere wijziging         | ★★★★★          |

---

## Hoe maak ik zelf een nieuwe skill?

Maak een nieuw bestand in `.cursor/skills/` met deze structuur:

```markdown
# Naam van de skill (bijv. pydantic-model)

**Doel**: Korte beschrijving wat de skill doet.

**Wanneer gebruiken**: Wanneer de gebruiker ...

**Instructies**:
1. ...
2. ...
3. ...

**Voorbeeld**:
User: "Maak een TradeSignal model"
Agent: [past de skill toe en genereert perfect Pydantic model]
```

---

## Aanbevolen mapstructuur voor LUMINA

```
Lumina/
├── .cursorrules
├── .cursor/
│   ├── skills/
│   │   ├── token-efficiency.md
│   │   ├── pydantic-model.md
│   │   ├── test-scaffolding.md
│   │   ├── risk-safety-review.md
│   │   ├── adr-writer.md
│   │   └── constitution-guard.md
│   └── rules/                    ← optioneel voor extra rules
│       ├── risk.md
│       └── event-bus.md
├── lumina_core/
├── tests/
├── docs/
│   └── adr/
└── config/
```

---

## Pro Tips voor maximale token-efficiëntie

1. **Maak skills specifiek** — hoe specifieker, hoe minder tokens je verspilt aan herhaling.
2. **Gebruik `todo_write` altijd** bij Complex/Safety taken (de skill dwingt dit af).
3. **Nieuwe chat = nieuwe bounded context** — dit is de grootste token-besparing.
4. **Combineer skills** — je kunt meerdere skills tegelijk actief hebben.
5. **Review de skill output** — na 1-2 weken zie je welke skills je het meest gebruikt en kun je ze optimaliseren.

---

## Klaar om te starten?

1. Maak de `.cursor/skills/` map
2. Plaats `token-efficiency.md`
3. Activeer in Cursor Settings
4. Test met `/token-efficiency`

Wil je dat ik de **andere 6 skills** (pydantic-model, test-scaffolding, etc.) nu voor je genereer? Dan heb je direct een complete set die perfect past bij LUMINA.

Zeg maar "maak ze allemaal" en ik lever ze direct aan.
