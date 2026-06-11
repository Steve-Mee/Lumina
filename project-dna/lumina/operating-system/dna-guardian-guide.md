# DNA Guardian – Gebruikershandleiding (v1)

Dit document legt uit hoe je de DNA Guardian effectief gebruikt als meet- en coachinstrument voor de continue verbetering van Lumina’s Project DNA.

## 1. Wat is de DNA Guardian?

De DNA Guardian is een tool die de kwaliteit en gezondheid van het Project DNA meetbaar maakt. Hij combineert:

- Structurele validatie (zijn alle verplichte bestanden aanwezig?)
- Truth Density scoring (zijn de teksten concreet, falsifieerbaar en evidence-based?)
- Health Score + trendlijnen
- Degradatie-detectie over tijd
- Optionele LLM-review (experimenteel)

Het doel is niet perfectie, maar **zichtbaarheid** en **stuurinformatie** voor gerichte evolutie.

## 2. Belangrijkste Metrics

| Metric                    | Wat meet het?                              | Goede score          | Slechte score       |
|---------------------------|--------------------------------------------|----------------------|---------------------|
| **Structural Health**     | Aanwezigheid van verplichte DNA-bestanden  | 10.0                 | < 8.0               |
| **Truth Density**         | Hoeveel bullshit / vaagheid / aspiratie    | ≥ 8.5                | < 7.0               |
| **DNA Health Score**      | Samengestelde score (50/50)                | ≥ 9.0                | < 8.0 (waarschuwing)|
| **Degradatie**            | Bestanden die structureel zwak blijven     | Geen waarschuwingen  | Herhaalde warnings  |

## 3. Hoe gebruik je de tool?

### Basis commando’s

```bash
# Gewone rapportage (mensvriendelijk)
python scripts/dna_guardian/validate_dna.py

# Machine-leesbaar (JSON)
python scripts/dna_guardian/validate_dna.py --json

# Maak een officiële evolution log entry + update agent-context (aanbevolen)
python scripts/dna_guardian/validate_dna.py --create-entry

# Met experimentele LLM review (alleen op zwakste bestand)
python scripts/dna_guardian/validate_dna.py --create-entry --llm-review
```

### Periodiek draaien (Increment 6)

Gebruik het script `scripts/dna_guardian/run_periodic.sh`:

```bash
./scripts/dna_guardian/run_periodic.sh
./scripts/dna_guardian/run_periodic.sh --llm-review
```

Voorbeeld cron (dagelijks om 09:00):

```cron
0 9 * * * cd /path/to/ninjatraderai_bot && ./scripts/dna_guardian/run_periodic.sh >> logs/dna_guardian.log 2>&1
```

## 4. Hoe interpreteer je de output?

### Groene situatie
- Health Score ≥ 9.0
- Geen degradatie-waarschuwingen
- Truth Density van focus-bestand ≥ 8.5

→ Je kunt rustig verder evolueren.

### Oranje situatie (aandacht nodig)
- Health Score tussen 8.0 en 9.0
- Eén bestand herhaaldelijk zwakst (3+ scans)

→ Prioriteer verbetering van dat specifieke bestand voordat je grote nieuwe dingen toevoegt.

### Rode situatie
- Health Score < 8.0
- Meerdere degradatie-waarschuwingen

→ Stop met grote architectuurwijzigingen. Eerst de DNA-kwaliteit herstellen.

## 5. Hoe volg je aanbevelingen op?

De Guardian geeft altijd een “Recommended Focus”. De juiste reactie is meestal:

1. Open het genoemde zwakste bestand.
2. Vraag jezelf (of een LLM): “Welke claims hier zijn niet falsifieerbaar of meetbaar?”
3. Maak een kleine, gerichte verbetering (hypothese + meetbaar signaal toevoegen).
4. Run de Guardian opnieuw met `--create-entry`.
5. Documenteer de verbetering in `evolution/log/`.

## 6. Beste practices

- Gebruik altijd `--create-entry` als je een meta-verbetering doet. Dit houdt de historie schoon.
- Gebruik `--llm-review` spaarzaam en alleen als je een goed lokaal model hebt draaien.
- Behandel de LLM output als “tweede opinie”, nooit als waarheid.
- Als één bestand structureel zwak blijft (5+ scans), is dat een signaal dat er iets fundamenteels mis is met dat document of het proces eromheen.

## 7. Beperkingen (v1)

- Truth Density scoring is nog grotendeels heuristisch (met optionele LLM-laag).
- De tool meet vooral *tekstuele* kwaliteit, niet per se of de inhoud in de praktijk goed werkt.
- LLM-review is experimenteel en kan hallucineren.

---

*Eerste versie geschreven als onderdeel van Increment 7 (2026-05-30).*