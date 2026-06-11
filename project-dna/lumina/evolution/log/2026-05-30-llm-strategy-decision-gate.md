# 2026-05-30 — Decision Gate: LLM Review Strategy voor de DNA Guardian

**Context**: Als onderdeel van de extreme first-principles acceleratie (Phase 1) moeten we een harde beslissing nemen over de toekomst van de LLM-laag in de Guardian.

## Verzamelde Data tot nu toe (calibratie runs)

**Run 1 (oude prompt)** – evolutionary-debt.md
- Heuristiek 7.0 → LLM 6.0 (conf 0.8)
- Sterke punten: goed in aspirational vs falsifiable.
- Zwakke punten: oppervlakkig op concrete oplossingen.

**Run 2 (oude prompt)** – self-improvement-protocol.md
- Heuristiek 7.9 → LLM 8.5 (conf 0.9)
- Positief: hogere score dan heuristiek, goede catch op missing metrics.

**Run 3 (nieuwe extreme prompt)** – self-improvement-protocol.md
- Heuristiek 8.6 → LLM 6-7 (conf 0.9)
- Kritiek op: vague language, gebrek aan specifieke falsifiability criteria, Evolvability Score niet duidelijk genoeg, te verbose.

**Algemene observaties**:
- De LLM is consistent goed in het signaleren van "gebrek aan meetbaarheid en concrete criteria".
- De kwaliteit van de output is sterk afhankelijk van de prompt.
- Zelfs met een sterk verbeterde prompt blijft de LLM kritischer dan de heuristiek op dit moment.
- Actionability van de bevindingen is matig tot goed (het wijst problemen aan, maar geeft niet altijd de beste oplossing).

## Opties op tafel

**Optie A: Double down op lokale LLM (huidige pad)**
- Voordelen: Zero marginal cost, data stays local, past bij onze stack.
- Nadelen: Huidige modellen (zelfs qwen3.5:9b) lijken moeite te hebben met de diepgang die we nodig hebben voor een "world-class reviewer".
- Vereist: Zeer zware investering in prompting, few-shot, RAG op onze eigen DNA, en mogelijk fine-tuning.

**Optie B: Hybrid model (lokaal + sterk cloud model)**
- Voordelen: Beste van twee werelden. Lokaal voor routine, sterk model (Grok / Claude / etc.) voor diepe reviews op de zwakste bestanden.
- Nadelen: Kosten, latency, data leakage risico (moet goed gemanaged worden).
- Vereist: Goede fallback + duidelijke policy wanneer welk model wordt gebruikt.

**Optie C: LLM review de-emphasizen / pauzeren**
- Focus volledig op heuristiek + menselijke reviews + betere structuur in de DNA bestanden zelf.
- LLM alleen gebruiken voor ad-hoc analyses buiten de Guardian.

## Aanbeveling (eerste versie)

Op basis van de huidige data en de extreme doelstelling (5-10x verbeteringssnelheid):

**Tijdelijke aanbeveling: Ga door met Optie A (double down lokaal), maar met een harde 14-dagen evaluatie deadline.**

Redenen:
- We hebben de infrastructuur al staan.
- De huidige prompt upgrade laat zien dat er nog veel winst te halen is in prompting alleen.
- Een sterke lokale reviewer zou een echt moat zijn.

**Actieplan bij deze keuze**:
1. Bouw een serieuze prompt + few-shot library (minstens 5-8 goede voorbeelden van sterke reviews).
2. Voeg RAG toe: de LLM krijgt relevante stukken uit truth-metrics.md, constitution, en recente goede evolution entries als context.
3. Na 10-15 nieuwe reviews met de verbeterde setup: harde meting van actionability (menselijke score 1-10 per finding).
4. Als gemiddelde actionability < 7.0 → switch naar Optie B of C.

Als we na 14 dagen geen duidelijke sprong in kwaliteit zien, moeten we eerlijk zijn en de scope van LLM review sterk inperken of hybrid maken.

---

Dit is de formele Decision Gate. Feedback en beslissing gewenst.