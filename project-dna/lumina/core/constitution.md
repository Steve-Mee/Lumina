# Lumina Constitution (Core Invariants)

**Status**: Near-immutable. Changes require exceptional justification, broad review, and explicit superseding entry in the evolution log.

This document defines the non-negotiable laws of the Lumina project. Everything else (principles, architecture, protocols, processes) must serve these invariants.

## Fundamental Invariants

1. **Kapitaalbehoud is heilig in REAL mode**
   - Geen enkele mutatie, strategie of proces mag REAL kapitaal in gevaar brengen zonder expliciete shadow deployment + human approval gates.
   - Fail-closed is de default in alle REAL-paden.

2. **Evolution is the primary mechanism of improvement**
   - We verbeteren door kleine, meetbare, traceerbare stappen — niet door grote rewrites of heroïsche fixes.
   - Het systeem moet over tijd makkelijker (niet moeilijker) worden om te evolueren.

3. **Truth-seeking > performance chasing**
   - Alle claims, metrics en beslissingen moeten eerlijk, falsifieerbaar en evidence-based zijn.
   - Optimisme over backtests, risico of eigen prestaties is verboden.

4. **Modulariteit en bounded contexts zijn heilig**
   - Geen god-files of god-modules.
   - Alle significante functionaliteit moet in kleine, testbare, vervangbare componenten met duidelijke interfaces leven.

5. **Veiligheid en observability gaan vóór evolutie**
   - De Safety Layer (Constitution + ConstitutionalGuard + Admission Chain) mag nooit verzwakt worden door nieuwe features of "snellere" evolutie.

6. **SIM/Paper vs REAL scheiding is absoluut**
   - SIM en Paper zijn laboratoria voor radicale experimentatie.
   - REAL is een fort. De scheiding tussen beide moet expliciet, geautomatiseerd en onontkoombaar zijn.

## Veranderregels

- Wijzigingen aan dit document vereisen:
  - Een expliciete "voor/na" hypothese + falsifieerbare voorspelling.
  - Toepassing van het Recursive Self-Improvement Protocol (inclusief Plan Mode).
  - Een entry in de evolution log die de reden, impact en rollback-pad beschrijft.
  - Sterke aanbeveling voor human review.

Dit document heeft prioriteit boven alle andere project-dna bestanden en alle code.

---

*Laatste update: 2026-05-29 (initiële versie als onderdeel van DNA 2.0 redesign)*