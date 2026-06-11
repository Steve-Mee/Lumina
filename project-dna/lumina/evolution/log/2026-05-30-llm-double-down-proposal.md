# 2026-05-30 — Voorstel: Double Down op Lokale LLM Review (Optie A) met Harde 14-dagen Evaluatie

**Besluitpunt**: Decision Gate LLM Strategy  
**Aanbevolen optie**: Optie A (Double down lokaal) met strikte evaluatieperiode.

## Samenvatting van de Aanbeveling

We gaan door met de lokale LLM-aanpak (momenteel gebaseerd op Ollama + qwen3.5:9b en vergelijkbare modellen), maar met een veel agressievere en gestructureerde verbeteringsaanpak dan tot nu toe.

**Waarom niet direct hybrid of de-emphasize?**
- We hebben de lokale infrastructuur al draaiende en goedkoop.
- De huidige data toont aan dat prompting nog significant meer waarde kan opleveren (de laatste prompt-upgrade liet al verschil zien).
- Een sterke lokale reviewer zou een echt strategisch voordeel zijn (zero cost, zero leakage, volledige controle).
- Hybrid of cloud-opties brengen nieuwe risico's (kosten, latency, data) die we pas serieus willen introduceren als de lokale aanpak écht gefaald heeft.

## Voorstel: 14-dagen "LLM Review Excellence Sprint"

### Doel
Binnen 14 dagen de actionability en betrouwbaarheid van de LLM-review laag significant verhogen, met een heldere go/no-go beslissing aan het einde.

### Succes criteria (harde meetlat)
- Gemiddelde **actionability score** (menselijk beoordeeld op schaal 1-10) over de laatste 12-15 reviews ≥ **7.5**.
- Minstens 60% van de LLM-bevindingen worden als "direct bruikbaar" of "hoogwaardig" beoordeeld in de volgende evolution entries.
- De LLM-score begint structureel hoger te liggen dan de heuristiek op de zwakste bestanden (of we begrijpen waarom dat niet het geval is).

### Wat we gaan doen (concrete implementatieplan)

#### Week 1 (Dagen 1-7) — Fundering & Prompt Engineering
1. **Prompt v3.0 (Extreme versie)**
   - Uitbreiden met expliciete chain-of-thought instructies.
   - Verplicht maken dat de LLM relevante stukken uit `truth-metrics.md` en recente goede evolution entries betrekt.
   - Toevoegen van "Few-shot" voorbeelden (minstens 4-6 sterke voorbeelden van goede reviews).
   - Duidelijke output structuur die beter aansluit bij wat we later willen meten (actionability + concrete suggesties).

2. **Few-shot Library opbouwen**
   - Verzamelen van 6-8 van de beste LLM-reviews tot nu toe (inclusief menselijke beoordeling).
   - Deze opslaan in een dedicated map (`project-dna/lumina/operating-system/llm-review-examples/`).
   - De Guardian kan deze later dynamisch inladen als context (simpele RAG).

3. **Context Injection (simpele RAG)**
   - Bij elke review automatisch de volgende context meesturen:
     - Recente definitie van Evolvability Score (uit self-improvement-protocol.md).
     - Kernstukken uit `truth-metrics.md`.
     - 1-2 recente sterke evolution entries als voorbeeld van goede stijl.

#### Week 2 (Dagen 8-14) — Intensieve Calibratie & Meting
4. **Intensief review programma**
   - Minstens 12-15 nieuwe reviews draaien op de huidige zwakste bestanden (en een paar sterke bestanden ter vergelijking).
   - Iedere review krijgt een menselijke actionability score (1-10) + korte motivatie.

5. **Harde evaluatie**
   - Na 14 dagen: volledige analyse publiceren (vergelijkbaar met deze Decision Gate).
   - Beslissing:
     - **Go** → Doorgaan met lokale aanpak + verdere optimalisatie.
     - **No-go** → Overschakelen naar Optie B (Hybrid) of C.

### Verantwoordelijkheden & Tempo
- Iedere 2-3 dagen een nieuwe calibratie batch + update entry.
- Alle data en scores worden openbaar vastgelegd in `evolution/log/`.
- Geen suikercoating: als de kwaliteit na 14 dagen niet significant beter is, stoppen we met deze richting.

## Risico's & Mitigatie
- Risico: Zelfs met betere prompting blijft de kwaliteit matig → Mitigatie: Harde 14-dagen deadline + expliciete no-go criteria.
- Risico: Te veel tijd besteed aan prompting in plaats van echte DNA verbeteringen → Mitigatie: De Debt Destruction Sprints blijven parallel lopen met dezelfde prioriteit.

## Volgende Concrete Stappen (nu starten)

1. **Vandaag / morgen**: Prompt v3.0 implementeren in `validate_dna.py` + eerste versie van de few-shot library aanmaken.
2. **Binnen 48 uur**: Eerste 4-5 reviews draaien met de nieuwe setup + publiceren.
3. **Binnen 7 dagen**: Volledige RAG-achtige context injection werkend maken.
4. **Dag 14**: Formele evaluatie entry publiceren met go/no-go beslissing.

Dit voorstel is streng, meetbaar en in lijn met de extreme acceleratie-doelstelling.

---

*Geschreven als directe uitvoering van de extreme first-principles plan.*