---
name: token-efficiency
description: >
  Handhaaft de token-efficiënte workflow voor Lumina. Zorgt voor juiste taakclassificatie,
  Plan Mode gebruik, todo_write discipline, strikte modelkeuze en context management.
  Deze skill is leidend voor alle agents (Grok Build en Cursor).
---

# Token Efficiency Skill (v2.0)

**Doel**: Zorgt dat iedere AI-agent (Grok Build & Cursor) **altijd** de meest token-efficiënte en veilige workflow volgt.

**Primaire bron**: `project-dna/lumina/AGENTS.md` (sectie 3)

**Wanneer gebruiken**: Altijd actief (automatisch of via `/token-efficiency`).

---

## 1. Taakclassificatie (Verplicht als eerste actie)

Classificeer de taak **hardop** volgens onderstaande tabel:

| Klasse              | Criteria                                           | Modus                    | Model-keuze          | Strategie                              |
|---------------------|----------------------------------------------------|--------------------------|----------------------|----------------------------------------|
| **Simple**          | < 3 bestanden, pure edit/refactor                  | Direct                   | Goedkoop model       | Direct uitvoeren                       |
| **Medium**          | 3-6 bestanden, duidelijke scope                    | **Plan Mode**            | Snel model           | Plan → uitvoering                      |
| **Complex**         | Nieuwe laag, integratie, architectuur              | **Plan Mode + todo**     | Premium model        | Plan + todo + user bevestiging         |
| **Safety-Critical** | Risk, Constitution, REAL mode, kapitaalbehoud      | **Plan Mode + todo**     | **Alleen Premium**   | Altijd Plan + human review             |

**Zeg altijd**:  
"Ik classificeer deze taak als **[Klasse]**. Strategie: [korte beschrijving]."

---

## 2. Verplichte Workflow

1. **Classificeer** de taak (eerste output).
2. **Start in Plan Mode** bij Medium/Complex/Safety-Critical.
3. **Gebruik `todo_write`** bij ≥3 stappen of Safety-Critical werk.
4. **Nieuwe chat = nieuwe bounded context** (belangrijkste token-besparing).
5. Na elke sub-taak: `ruff + mypy --strict + pyright + relevante tests`.
6. Rapporteer geschat vs werkelijk token-verbruik bij Complex/Safety-Critical taken.

---

## 3. Model-keuze (Strikt)

- **Nooit** premium model gebruiken voor:
  - Verkenning, simpele edits, debugging of "even iets checken".
- **Alleen** premium model (Sonnet 4.5 / Opus / GPT-5 thinking) bij:
  - Complex of Safety-Critical taken + expliciete user bevestiging.

---

## 4. Context Management (Nooit breken)

- **Nieuwe chat = nieuwe bounded context**.
- Nooit hele chatgeschiedenis meenemen naar een nieuwe taak.
- Laad bij complexe taken eerst de relevante skills uit `project-dna/lumina/operating-system/skills/`.

---

## 5. Refactor PR Strategie (Automatisch bij grote refactors)

Bij refactors > 1200 regels of complexe module-splitsingen:

1. Splits altijd in **2 PR’s**:
   - **PR 1 – Core Split**: Nieuwe bestanden + thin proxies + basis functionaliteit.
   - **PR 2 – Docs & Validatie**: `docs/architecture.md` update + tests + ruff/mypy.

2. Geef direct twee kant-en-klare prompts mee.

---

## 6. Nooit doen

- Nooit een complexe taak starten zonder Plan Mode + todo list.
- Nooit een taak met > 5 stappen in één prompt proppen zonder opsplitsing.
- Nooit optimistische assumpties maken over token-verbruik.
- Nooit context rot veroorzaken.

---

**Deze skill garandeert 40-60% reductie in premium token-verbruik** met behoud van maximale kwaliteit en veiligheid.

*Versie 2.0 — Geoptimaliseerd voor centrale AGENTS.md (juni 2026)*