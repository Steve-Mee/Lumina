# Contributing to LUMINA

Welkom. Als je dit leest, denk je waarschijnlijk groter dan gemiddeld — goed zo. Lumina is geen hobbyscript: het is een **zelflerend organisme** dat echte kapitaalstromen kan raken. Daarom is deze guide **warm over de ambitie** en **hard over veiligheid en discipline**.

---

## 1. Welkom & missie

**LUMINA** wil het objectief beste zelf-lerende, zelf-evoluerende AI-daytrading systeem voor NinjaTrader zijn. We streven naar de **1% die structureel overleeft** — niet door geluk of een enkele glanzende backtest, maar door:

- **Extreme intellectual honesty** — alleen claims die data en audits dragen.
- **Rigoureuze testing** — kwaliteit is architectuur, geen bijlage.
- **Radicale creativiteit** — vooral in SIM/Paper, waar het organisme mag experimenteren zonder ketenen.

**Kapitaalbehoud is heilig in REAL mode.** Jouw bijdrage moet Lumina **sterker, veiliger en evolueerbaarder** maken — zie ook het leidende bestand [`.cursorrules`](.cursorrules).

---

## 2. Hoe we werken (core principles)

| Principe | Wat we verwachten |
|----------|-------------------|
| **Extreme intellectual honesty** | Geen verborgen risico’s, geen cosmetische metrics. Als iets fragiel is, zeg het — en los het structureel op. |
| **ADR-gedreven ontwikkeling** | Grote of grensverleggende beslissingen worden **eerst** vastgelegd als Architecture Decision Record. Zie sectie 4. |
| **Fail-closed & Safety First** | Bij twijfel: blokkeren en auditen, niet “doorlaten”. REAL heeft strengere regels dan SIM. |
| **Radicale creativiteit + first principles** | Simpele, elegante oplossingen; als je iets radicaals voorstelt, lever je **bewijs, tests en governance** mee. |

---

## 3. Development workflow

### Branch naming

Gebruik een duidelijk prefix:

| Prefix | Gebruik |
|--------|---------|
| `feature/` | Nieuwe functionaliteit |
| `refactor/` | Structurele verbetering zonder gedrag te breken (idealiter) |
| `safety/` | Alles wat constitution, sandbox, shadow, risk gates of REAL-paden raakt |

Voorbeelden: `feature/event-bus-metrics`, `refactor/risk-context-imports`, `safety/constitution-principle-16`.

### Commit messages

- **Imperatief, kort onderwerp** — bv. `Add risk gate telemetry for REAL mode`.
- **Waarom** in de body als het niet triviaal is.
- **ADR-referentie** als de commit bij een ADR hoort:  
  `Refs: docs/adr/0001-bounded-contexts-central-event-bus.md`  
  of `ADR-0003` in de eerste regel als je team dat zo afsprak.

### Checks vóór je een PR opent

Voer lokaal uit (vanaf de repository-root):

```bash
ruff check .
mypy .
pytest -m "not slow"
```

### Code quality triage (`scripts/fix_code_quality.py`)

Voor een **gestructureerde** pas over lint, types en (optioneel) falende tests — met **root-cause narrative** (bounded context, ontwerp vs bug) en **extreme intellectual honesty** — gebruik:

```bash
python scripts/fix_code_quality.py --dry-run
```

- **Standaard:** analyse-only (`--dry-run`); schrijft `quality_fix_report.md` in de repo-root met samenvatting, RCA en voorstellen.
- **`--apply`:** past alleen **objectief veilige** Ruff-autofixes toe na bevestiging (`--confirm batch|issue`, of `-y` voor niet-interactief). Het script voegt **geen** `# noqa` of `type: ignore` toe — typefouten en testfails zijn **handmatig** op te lossen volgens het rapport.
- **`--category`:** `all` | `lint` | `type` | `test` — beperk scope.
- **`--strict-mypy`:** strengere MyPy-pass (`--strict` op de CLI naast `mypy.ini`); sluit aan bij diepere contractreviews, los van CI die vaak de project-config gebruikt.
- **`--with-pyright` / `--no-pytest`:** optionele tools volgens je lokale setup.

Na wijzigingen met `--apply` draait het script standaard `pytest -m "not slow"` ter verificatie (uitschakelbaar met `--no-verify-tests`).

- **`ruff`** en **`mypy`** horen groen te zijn voor gewijzigde code.
- **`pytest -m "not slow"`** sluit de `slow`-marker uit (zware sims, lange runs); die horen in CI/nightly, niet per se op elke laptop-frequentie.

Pas je tests aan of voeg ze toe volgens de markers in `pytest.ini` (`unit`, `integration`, `slow`, …).

---

## 4. Architecture Decision Records (ADR)

### Wanneer schrijf je een ADR?

Schrijf een ADR als je **niet-triviale** architectuur raakt, bijvoorbeeld:

- Nieuwe bounded context, grens tussen domeinen, of significante wijziging aan de event bus.
- Nieuwe safety- of promotion-flow (constitution, sandbox, shadow, human approval).
- Contracten die anderen moeten volgen (topics, payloads, fail-closed regels).
- Brede refactors die het mentale model van het project veranderen.

**Geen ADR** voor: typo’s, kleine bugfixes zonder architectuurimpact, dependency bumps zonder gedragsverandering — tenzij de bump veiligheidskritisch is; gebruik je oordeel en wees eerlijk in de PR-beschrijving.

### Template gebruiken

Kopieer [docs/adr/0000-template.md](docs/adr/0000-template.md) naar een nieuw bestand in `docs/adr/` volgens de naamgeving **`000x-korte-titel.md`** (zie [docs/adr/README.md](docs/adr/README.md)).

Vul minimaal in:

- **Context** — probleem, risico’s, link met missie en first principles.
- **Decision** — concrete keuze, modules/contexts, fail-closed grenzen.
- **Consequences** — positief én negatief (intellectual honesty).
- **Alternatives considered** — waarom verworpen.
- **Links** — gerelateerde ADR’s, issues, runbooks.

### Een nieuwe ADR aanmaken

Gebruik het initializer-script — het kiest het volgende vrije **000x**-nummer, kopieert het template, zet titel en datum, werkt [`docs/adr/README.md`](docs/adr/README.md) bij en opent het bestand (als dat lukt in jouw omgeving):

```bash
python scripts/new_adr.py "Introduce Dynamic Kelly Sizing"
```

Handig als shell-alias (Linux/macOS/Git Bash):

```bash
alias new-adr='python scripts/new_adr.py'
```

Wil je geen editor-launch (alleen pad naar stdout): `python scripts/new_adr.py "Titel" --no-open`.

### Voorbeeldworkflow

1. **Ik wil X toevoegen** (bv. nieuw topic op de event bus met risk-impact).
2. **Eerst ADR** — open een PR of sectie in je branch met `docs/adr/0007-….md` die de beslissing vastlegt *voordat* of *samen met* de eerste serieuze code landt.
3. **Dan code** — implementatie volgt de ADR; afwijkingen = ADR aanpassen of nieuwe ADR, geen stille drift.

Zo blijft Lumina **navigeerbaar** voor de volgende contributor — die ben jij over zes maanden.

---

## 5. Self-evolution proces (wat jij moet weten)

LUMINA muteert eigen trading-DNA. Dat mag **niet** betekenen: “alles mag live”. Drie pijlers:

### Shadow deployment

Kandidaat-DNA draait **shadow** naast live strategie (SIM/PAPER-context): PnL en criteria worden bijgehouden. Promotie naar REAL vereist onder meer voldoende duur, volume en statistische onderbouwing — plus waar van toepassing **menselijke goedkeuring**. Zie [docs/adr/0002-shadow-deployment-human-approval.md](docs/adr/0002-shadow-deployment-human-approval.md).

### Trading Constitution

Machine-leesbare principes in [`lumina_core/safety/trading_constitution.py`](lumina_core/safety/trading_constitution.py): mutaties en promoties moeten principes passeren. **Fail-closed**: een check die faalt = geen uitvoering. Mode-aware (REAL strenger).

### Approval Gym

[`ApprovalGym`](lumina_core/evolution/approval_gym.py) genereert **compacte approval drills** (voorstellen op basis van historische of gesimuleerde DNA) en legt antwoorden vast — een trainingsspier voor menselijke go/no-go naast geautomatiseerde gates. [`ApprovalGymScheduler`](lumina_core/evolution/approval_gym_scheduler.py) koppelt dit aan planning (o.a. operator-/Telegram-workflows). Contributors: raak dit aan met **respect voor REAL**; wijzig gedrag alleen met tests en ADR waar het gedrag user-facing is.

Meer diepgang: [docs/AGI_SAFETY.md](docs/AGI_SAFETY.md).

---

## 6. Code style & kwaliteit

- **Leidend gedrag** — [`.cursorrules`](.cursorrules): Python 3.13+, type hints, ruff, mypy, tests met markers.
- **Type hints** — overal waar het zinvol is; Pydantic waar contracts nodig zijn.
- **Docstrings** — voor publieke API’s en niet-obvious invarianten; geen ruis rond triviale getters.
- **Tests** — nieuwe logica krijgt tests; kritieke paden (risk, safety) krijgen **extra** aandacht.
- **Geen god-classes** — split verantwoordelijkheden; gebruik **bounded contexts** en event-driven patronen waar dat past ([docs/architecture.md](docs/architecture.md), ADR 0001 / 005).

---

## 7. Pull request richtlijnen

### Beschrijving

Leg uit **wat**, **waarom**, en **welk risico** (zeker voor REAL/safety). Link naar issues en ADR’s.

### Suggestie-checklist (kopieer naar je PR)

```markdown
## PR checklist

- [ ] ADR toegevoegd/bijgewerkt indien architectuur- of safety-impact
- [ ] `ruff check .` en `mypy` OK op relevante paden
- [ ] `pytest -m "not slow"` OK (of gemotiveerd waarom niet)
- [ ] Safety impact beschreven (REAL / SIM / constitution / shadow)
- [ ] Geen secrets of lokale paden gecommit
```

### Review criteria (wat reviewers zoeken)

- **Klopt het met de ADR?** Geen stille scope creep.
- **Fail-closed** op nieuwe gates — geen “hopelijk OK” paden in REAL.
- **Tests** dekken het gedrag en de foutpaden die je introduceert.
- **Leesbaarheid** — over vijf jaar nog begrijpelijk.

---

## 8. Veelgestelde vragen

### Mag ik direct naar `main` pushen?

**Nee** — werk via branches en PR’s. Direct pushen omzeilt review en CI; dat past niet bij een kapitaal-kritisch systeem.

### “Ik wil snel een fix” — mag dat zonder ADR?

Kleine, lokale bugfix **zonder** architectuurimpact: ja, met duidelijke PR en tests. **Grote** of **grenswijzigende** changes: **eerst ADR** (of uitbreiding van bestaande ADR), dan code.

### Hoe test ik de Constitution?

- **Unit/integration tests** onder `tests/` die `TradingConstitution` / `ConstitutionalGuard` aanroepen met representatieve payloads en **verwachte blocks** op FATAL-regels.
- Draai relevante subsets met `pytest` en zoek naar bestaande safety-tests als voorbeeld.
- Raadpleeg [docs/AGI_SAFETY.md](docs/AGI_SAFETY.md) voor de fasering (pre-mutation, sandbox, pre-promotion).

### Waar documenteer ik een operationele runbook-actie?

`docs/` — bv. release-workflow, production setup — en link vanuit je ADR of PR als het terugkerend werk beschrijft.

---

## Nog één ding

We willen dat je **radicaal** denkt en **elegant** bouwt — maar nooit ten koste van **intellectual honesty** of **kapitaal in REAL**. Als dat tension voelt, goed: dat is het teken dat je op het juiste niveau werkt.

**Vragen?** Open een issue met het label `question` of vraag in je PR om een pair-review op safety-kritieke delen.

— *LUMINA Engineering*
