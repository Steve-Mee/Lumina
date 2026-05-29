# Recursive Self-Improvement Protocol

**Minimal Version** — Voor het veilig en gedisciplineerd verbeteren van instructies, Project DNA en agent guidance.

## Doel
Dit protocol zorgt ervoor dat verbeteringen aan hoe Lumina zichzelf bestuurt en documenteert (DNA, AGENTS.md, .cursorrules, skills) op dezelfde manier gebeuren als veranderingen aan de trading logica: klein, traceerbaar, met Plan Mode en expliciete reversibility.

## Scope
Van toepassing op:
- Alle bestanden onder `project-dna/`
- Root `AGENTS.md`
- `.cursorrules` (indien het agent-gedrag rond architectuur, risico of evolutie raakt)
- Kern-skills in `.cursor/skills/` die planning, risk, constitution of self-improvement beïnvloeden

Niet van toepassing op normale feature-ontwikkeling of trading-strategie wijzigingen.

## Wanneer en hoe een verbetering voorstellen

### Wanneer mag een agent of mens een voorstel doen?
- Een verwijzing in AGENTS.md of DNA wijst naar iets dat niet bestaat.
- Er is herhaalde frictie of onduidelijkheid bij het volgen van de huidige instructies.
- Er is een duidelijke kans om evolutie veiliger, sneller of eerlijker te maken.
- Er wordt een anti-patroon ontdekt in hoe we onszelf documenteren of besturen.

### Hoe stel je een verbetering voor?
1. **Start altijd in Plan Mode** (verplicht).
2. Classificeer de impact:
   - **Small**: Verduidelijking of kleine toevoeging.
   - **Medium**: Structurele wijziging in DNA of significante update van AGENTS.md / .cursorrules.
   - **Large**: Fundamentele verandering in governance of principes.
3. Formuleer een heldere hypothese: wat is het probleem met de huidige versie en waarom is de nieuwe beter?

## Verplichte stappen

- **Plan Mode** is altijd verplicht bij meta-wijzigingen. Geen uitzonderingen.
- **Evolution-log entry** is verplicht. Voeg direct een entry toe aan `project-dna/evolution-log.md` met:
  - Datum
  - Wat is er veranderd
  - Waarom (probleem of kans)
  - Verwacht effect
  - Hoe we weten of het werkt
  - Hoe de wijziging kan worden teruggedraaid of vervangen

## Documentatie en rollback

- Iedere meta-wijziging wordt vastgelegd via de evolution-log entry.
- Bij voorkeur: kleine incrementele wijzigingen (liever een nieuw klein bestand dan een grote rewrite).
- **Rollback**: Een meta-wijziging wordt teruggedraaid door het bestand terug te zetten of te vervangen én een nieuwe evolution-log entry toe te voegen die expliciet aangeeft dat de vorige wijziging is gesuperseded, met reden en vervanger.

Git + de evolution-log vormen samen de audit trail.

## Extra checks bij governance of risk

Wanneer een wijziging aan instructies of DNA invloed kan hebben op:
- Hoe agents omgaan met risk, constitution of Real-mode veiligheid, of
- Governance-processen (bijv. promotie, approval, Final Arbitration)

Dan geldt:
- Verplicht toepassen van de skills `constitution-guard` en `risk-safety-review`, ook al raakt de wijziging alleen documentatie of instructies.
- Human review wordt sterk aanbevolen bij Medium en Large wijzigingen.

## Voorbeeld evolution-log entry

```markdown
### 2026-05-30
- **Introduced minimal Recursive Self-Improvement Protocol**
  - Created project-dna/lumina/self-improvement-protocol.md
  - Waarom: AGENTS.md verwees naar een protocol dat niet bestond als concreet document.
  - Effect: Eerste expliciete proces voor het evolueren van eigen instructies en DNA.
  - Reversibility: Vervang of verwijder het bestand + voeg een superseding log entry toe.
```

---

Dit is de minimale, bruikbare versie. Verdere verfijning gebeurt via dit protocol zelf.