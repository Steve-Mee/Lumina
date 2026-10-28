---
name: validation-rigor
description: >
  Dwingt de Validation Gate uit RESEARCH_CHARTER.md (repo-root SSOT) af.
  Gebruik bij strategy, backtest, evolution, promotion, birth, signal of fitness.
  Rapporteert DSR, PBO, walk-forward efficiency en de OOS-distributie. Bij twijfel: reject.
---

# Validation Rigor Skill (v1.0, 2026-10-28)

Bron van de regels: [`RESEARCH_CHARTER.md`](../../../../RESEARCH_CHARTER.md). Bij conflict wint het charter.

Phase 1 freeze: agents mogen geen nieuwe signalen schrijven tot Phase 1 van `lumina_research/` klaar is. Bouw niet verder op `archive/birth-v1/`.

## Triggers
strategy, backtest, evolution, promotion, birth, signal, fitness.

## Instructie
Dwing altijd de Validation Gate af voordat iets gepromoveerd wordt of live exposure krijgt. Alle punten zijn verplicht:

1. Walk-forward over minimaal 5 tot 8 niet-overlappende OOS-vensters, bij voorkeur rolling.
2. CPCV met purge en embargo. Rapporteer de volledige verdeling van de OOS-resultaten, niet één pad.
3. Deflated Sharpe Ratio, gecorrigeerd voor het aantal uitgevoerde trials.
4. PBO: liefst onder 0.25, harde reject boven 0.50.
5. Realistische kosten vanaf dag 1: commissie, halve spread, dynamische slippage en een eenvoudige market-impact.
6. Regime-robuustheid, minstens voor volatiliteit en trend.

## Verplicht rapport
Elk resultaat bevat:
- de DSR en het aantal trials;
- de PBO;
- de walk-forward efficiency (OOS ten opzichte van IS);
- de OOS-distributie (mediaan, spreiding, het slechtste venster en het aandeel positieve vensters);
- de kosten per type;
- het resultaat per regime.

## Beslisregel
- Er ontbreekt een metriek, of er is twijfel: **REJECT**.
- De PBO is hoger dan 0.50: **REJECT**.
- De claim is gebaseerd op één mooie backtest of op in-sample PnL: **REJECT**.
- Bij een reject stel je altijd een compliant alternatief voor.
- De Risk Core wordt nooit aangeraakt. Agents mogen enkel voorstellen.
