# Onderzoeksteam (via Steve 2026-10-29 19:24; NIET Steve's mening): null-only validatie
1 ES A2 6/32 na v2: geen aparte reparatie; strict edge 0/32 volstaat; A2 blijft diagnostiek.
2 0/32 < 5% aanvaardbaar, met power-caveat; strict gate niet versoepelen. Bij positive control expliciet checken dat planted edge >= drempel haalt; null 0/32 + planted niet gedetecteerd = power-probleem.
3 Volgende stap: positive control (planted edge bekende grootte) onder midpoints fade 1.0/1.2, breakout 1.8/0.9 op ES-tape; geen full strategy-run. Pas bij clean detectie + stille null mag een limited strategy-run volgen (aparte stap). NQ dicht.
