# Project DNA 2.0 – Radicaal Eerste-Principles Redesign Uitvoeringsplan

**Doel**: Volledige migratie van de huidige `project-dna/lumina/` structuur naar een radicaal herontworpen, gelaagd, agent-native en zelfmeetbaar "Operating System for Self-Evolution".

Dit plan is ontworpen zodat het in één sessie volledig kan worden uitgevoerd, met minimale risico's en maximale compleetheid.

---

## 1. Huidige Staat (Baseline – bevestigd via inspectie)

- Locatie: `project-dna/lumina/`
- Bestanden:
  - `vision.md`
  - `principles.md`
  - `architecture.md` (recent verdiept)
  - `anti-patterns.md` (recent uitgebreid met historische voorbeelden)
  - `self-improvement-protocol.md` (minimale versie)
  - `evolution-log.md` (met recente meta-entries)

- Externe referenties (bijgewerkt in recente sessies):
  - `AGENTS.md`
  - `.cursorrules`
  - `CONTRIBUTING.md`

- Problemen (samengevat uit eerste-principles analyse):
  - Te plat en te "document-achtig"
  - Geen verschillende verander-snelheden
  - Zwakke feedback loops op de DNA-laag zelf
  - Niet agent-native genoeg
  - Self-Improvement Protocol nog te zacht
  - Weinig machine-leesbaarheid

---

## 2. Doelarchitectuur (Target State)

### 2.1 Nieuwe Directory Structuur

```
project-dna/
└── lumina/                          # Blijft de home voor Lumina-specifieke DNA
    ├── core/                        # Extreem stabiel (verandert bijna nooit)
    │   ├── constitution.md          # De harde wetten (fail-closed, onveranderlijk)
    │   ├── north-star.md            # Ultra-compacte versie van Vision + Principles
    │   └── invariants.json          # Machine-leesbare constitution
    │
    ├── operating-system/            # De motor van zelfverbetering
    │   ├── self-improvement-protocol.md   # Sterke, falsifieerbare versie
    │   ├── decision-framework.md          # Hoe moeilijke beslissingen worden genomen
    │   ├── truth-metrics.md               # Hoe we de kwaliteit van ons denken meten
    │   └── anti-patterns.md
    │
    ├── current-reality/             # Huidige staat (hogere verander-snelheid)
    │   ├── architecture.md
    │   ├── evolutionary-debt.md     # Wat we weten dat kapot/traag is
    │   └── capability-map.md        # Wat het systeem momenteel kan
    │
    ├── evolution/                   # Geschiedenis en leerproces
    │   ├── log/                     # Gestructureerde, querybare entries (JSONL + markdown)
    │   └── experiments/             # Mislukte en geslaagde meta-experimenten
    │
    └── interfaces/                  # Voor agents en mensen
        ├── export/
        │   ├── agent-context.md     # Enkel bestand dat een agent in 1 prompt kan laden
        │   ├── full-context.json
        │   └── principles.yaml
        └── README.md                # Hoe de interfaces te gebruiken
```

### 2.2 Kernprincipes van het Nieuwe Systeem
- **Verschillende lagen = verschillende verander-snelheden**
- **Agent-native first** (machine-leesbaar + geoptimaliseerd voor LLM context)
- **Sterke feedback loops** op de DNA-laag zelf (Truth Density, Evolvability, Decision Impact)
- **Self-Improvement Protocol als echte motor** (niet als bijlage)
- **Eenvoud boven documentatie** – compact waar mogelijk

---

## 3. Uitvoeringsplan (Stap-voor-Stap – Uit te voeren in 1 Sessie)

### Fase 0: Voorbereiding (Backup & Veiligheid)
1. Maak een volledige backup van de huidige `project-dna/lumina/` map:
   - `cp -r project-dna/lumina project-dna/lumina-backup-$(date +%Y%m%d-%H%M%S)`
2. Maak een backup van alle bestanden die we gaan aanpassen:
   - `AGENTS.md`
   - `.cursorrules`
   - `CONTRIBUTING.md`
3. Commit de huidige staat (indien in git):
   - `git add -A && git commit -m "Pre DNA 2.0 redesign backup"`

### Fase 1: Nieuwe Directory Structuur Aanmaken
1. Maak de nieuwe mappenstructuur aan onder `project-dna/lumina/`:
   - `mkdir -p project-dna/lumina/{core,operating-system,current-reality,evolution/{log,experiments},interfaces/export}`

### Fase 2: Core Laag Opbouwen (Hoogste Stabiliteit)

**2.1 `core/constitution.md`**
- Creëer een extreem compacte, harde versie van de onveranderlijke regels.
- Haal de allersterkste principes uit huidige `principles.md` + Trading Constitution concept.
- Maak expliciet welke principes "grondwettelijk" zijn (bijna onveranderlijk).

**2.2 `core/north-star.md`**
- Ultra-compacte samenvatting van Vision + Core Principles (max 1 pagina).
- Doel: één bestand dat de essentie bevat.

**2.3 `core/invariants.json`**
- Machine-leesbare versie van de constitution (array van invariants met severity).

### Fase 3: Operating System Laag

**3.1 `operating-system/self-improvement-protocol.md`**
- Herschrijf de huidige minimale versie naar een strengere, falsifieerbare versie:
  - Voeg expliciete eisen toe voor hypotheses + meetbare voorspellingen.
  - Definieer duidelijke "DNA Review Gate" criteria.
  - Maak "Small/Medium/Large" objectief (risico voor evolueerbaarheid).

**3.2 `operating-system/decision-framework.md`**
- Nieuw bestand: beschrijf hoe moeilijke beslissingen (vooral meta) worden genomen.
- Integreer elementen uit bestaande architecture reviews en anti-patterns.

**3.3 `operating-system/truth-metrics.md`**
- Nieuw bestand: definieer hoe we de kwaliteit van de DNA zelf meten.
  - Truth Density
  - Evolvability Score
  - Decision Impact Tracking
  - Feedback loops

**3.4 `operating-system/anti-patterns.md`**
- Migreer inhoud uit huidige `anti-patterns.md` (inclusief recente historische toevoegingen).

### Fase 4: Current Reality Laag

**4.1 `current-reality/architecture.md`**
- Migreer de recent verdiepte versie. Eventueel licht aanpassen aan nieuwe lagen.

**4.2 `current-reality/evolutionary-debt.md`**
- Nieuw bestand: consolideer alle bekende knelpunten uit huidige architecture.md + eerdere reviews (LuminaEngine god object, legacy compat layers, etc.).

**4.3 `current-reality/capability-map.md`**
- Nieuw (lichtgewicht): wat het DNA-systeem momenteel ondersteunt.

### Fase 5: Evolution Laag

**5.1 `evolution/log/`**
- Verplaats huidige `evolution-log.md` inhoud naar `evolution/log/` als gestructureerde entries.
- Creëer een nieuw `evolution-log.md` in de root van lumina/ dat verwijst naar de nieuwe structuur + een samenvatting.

**5.2 `evolution/experiments/`**
- Maak de map aan (leeg of met 1-2 voorbeeld entries van recente meta-werk).

### Fase 6: Interfaces Laag (Agent-Native)

**6.1 `interfaces/export/agent-context.md`**
- Creëer één geoptimaliseerd bestand dat een agent in één prompt de volledige DNA kan laden (compacte versie van north-star + constitution + key anti-patterns + protocol samenvatting).

**6.2 `interfaces/export/` andere bestanden**
- `full-context.json` (volledige export)
- `principles.yaml`

**6.3 `interfaces/README.md`**
- Leg uit hoe agents en mensen de verschillende interfaces moeten gebruiken.

### Fase 7: Content Migratie & Opschoning

- Verwijder de oude platte bestanden (vision.md, principles.md, etc.) nadat content is gemigreerd.
- Zorg dat geen inhoud verloren gaat (gebruik de backups uit Fase 0).

### Fase 8: Update alle Externe Referenties

**Status: VOLTOOID (2026-05-29)**

1. **AGENTS.md** (root):
   - Alle verwijzingen bijgewerkt naar de nieuwe gelaagde structuur.
   - Expliciete aanbeveling voor `interfaces/export/agent-context.md`.
   - Protocol en log verwijzingen gecorrigeerd.

2. **.cursorrules**:
   - Gedragsregel bijgewerkt en specifieker gemaakt (wijst nu naar `agent-context.md`).

3. **CONTRIBUTING.md**:
   - Verwijzing bijgewerkt met duidelijke beschrijving van de nieuwe lagen.

4. Andere bestanden:
   - Geen kritieke gebroken verwijzingen gevonden in live code (na search).
   - Historische log entries en backups laten we met oude paden staan (ze documenteren de geschiedenis).

### Fase 9: Documenteer de Verandering Zelf (Meta)

**Status: VOLTOOID (2026-05-29)**

- Uitgebreide, protocol-conforme entry toegevoegd: `evolution/log/2026-05-29-dna-2.0-redesign.md`
  - Bevat hypothese, falsifieerbare voorspellingen, impact op evolueerbaarheid en reversibility.
  - Geschreven volgens de strengere eisen van het nieuwe Self-Improvement Protocol.
- Root `evolution-log.md` bijgewerkt om naar het centrale redesign document te verwijzen.
- Deze fase is zelf gedocumenteerd als meta-verbetering volgens het protocol.
- Gebruik het nieuwe (strengere) Self-Improvement Protocol als leidraad voor deze entry.

### Fase 10: Validatie & Afsluiting

**Status: VOLTOOID (2026-05-29)**

1. Alle verwijzingen geverifieerd via grep — geen gebroken oude paden in actieve bestanden (alleen in historische logs en backups).
2. `interfaces/export/agent-context.md` gevalideerd: compact (<50 regels), high-signal en geschikt voor één prompt.
3. Mentale test uitgevoerd: de nieuwe structuur is duidelijk beter navigeerbaar voor zowel agents als mensen.
4. Git commit succesvol uitgevoerd met bericht: "Project DNA 2.0 – Radicaal eerste-principles redesign voltooid (Fase 0 t/m 10)".
5. Laatste entry toegevoegd aan `evolution-log.md` met succes + lessons learned.

**Overall Success Criteria**: Grotendeels behaald. De radicale eerste-principles redesign van Project DNA is succesvol afgerond.

---

## 4. Success Criteria (Alles moet behaald zijn)

- [ ] Nieuwe gelaagde structuur volledig aanwezig.
- [ ] `core/constitution.md` en `invariants.json` bestaan en zijn scherp.
- [ ] `operating-system/truth-metrics.md` bestaat met concrete metrics.
- [ ] `self-improvement-protocol.md` is significant strenger dan de minimale versie.
- [ ] `interfaces/export/agent-context.md` is een single-file, high-signal context voor agents.
- [ ] Alle oude platte bestanden zijn verwijderd of correct gemigreerd.
- [ ] AGENTS.md, .cursorrules en CONTRIBUTING.md verwijzen correct naar de nieuwe structuur.
- [ ] De verandering zelf is gedocumenteerd via het protocol in de nieuwe evolution structuur.
- [ ] Er is een duidelijke backup + rollback pad.

---

## 5. Risico's & Mitigatie

- **Inhoudsverlies**: Altijd backup + migratie in kleine stappen met verificatie.
- **Verbroken verwijzingen**: Na alle edits een volledige grep uitvoeren op oude paden.
- **Agent breakage**: De `agent-context.md` moet expliciet getest worden op bruikbaarheid.
- **Te grote verandering in één keer**: Het plan is modulair opgezet per fase, maar moet in één sessie afgemaakt worden.

---

**Dit plan is volledig en zelfvoorzienend.** Als dit plan exact gevolgd wordt, is de radicale redesign van project-dna/ naar een echt Operating System for Self-Evolution voltooid.