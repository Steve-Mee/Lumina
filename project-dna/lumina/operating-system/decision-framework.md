# Decision Framework

Dit framework beschrijft hoe moeilijke beslissingen (vooral op meta-niveau) binnen Lumina worden genomen.

## Uitgangspunten

1. **First Principles** — Breek het probleem terug tot de fundamentele waarheden (uit constitution.md en north-star.md).
2. **Evidence > Intuïtie** — Iedere significante claim moet ondersteund worden door data, experimenten of expliciete aannames.
3. **Reversibility** — Geef altijd de voorkeur aan beslissingen die makkelijk ongedaan gemaakt of bijgestuurd kunnen worden.
4. **Evolvability Impact** — Vraag altijd: "Maakt deze beslissing het systeem in de toekomst makkelijker of moeilijker om te verbeteren?"

## Stappen voor Grote Beslissingen

1. **Probleemdefinitie** (First Principles)
   - Wat is het echte probleem, los van de voorgestelde oplossing?
   - Welke invarianten uit de Constitution worden geraakt?

2. **Opties genereren**
   - Genereer minimaal 3 serieuze alternatieven (inclusief "niets doen").

3. **Hypothese + Voorspelling**
   - Formuleer voor elke optie een duidelijke hypothese + falsifieerbare voorspelling (wat verwachten we over 3/6/12 maanden?).

4. **Risico & Reversibility Analyse**
   - Wat is de downside als we het mis hebben?
   - Hoe makkelijk kunnen we terug of bijsturen?

5. **DNA Check**
   - Past deze beslissing binnen de huidige principles, architecture en anti-patterns?
   - Zo niet: welke aanpassing aan de DNA is nodig, en via welk proces?

6. **Documentatie**
   - Leg de redenering, hypothese en voorspelling vast (bij voorkeur in de evolution log of een ADR).

7. **Review Gate**
   - Small: Zelf-review met expliciete hypothese.
   - Medium/Large: Volg het Recursive Self-Improvement Protocol + overweeg extra review (constitution-guard / risk-safety-review indien relevant).

## Voor Meta-Beslissingen (DNA, AGENTS.md, protocollen)

Extra eisen:
- Altijd starten in Plan Mode.
- Altijd een entry in de evolution log met hypothese + voorspelling.
- Overweeg een "DNA Impact Assessment" (hoe beïnvloedt dit onze toekomstige capaciteit om onszelf te verbeteren?).

---

Dit framework heeft prioriteit boven ad-hoc besluitvorming bij alles wat de lange-termijn evolueerbaarheid van Lumina raakt.