# Lumina Constitution (Core Invariants)

**Status**: Near-immutable. Changes require exceptional justification, broad review, and explicit superseding entry in the evolution log.

This document defines the non-negotiable laws of the Lumina project. Everything else (principles, architecture, protocols, processes) must serve these invariants.

## Fundamental Invariants

1. **Kapitaalbehoud is heilig in REAL mode**
   - Geen enkele mutatie, strategie of proces mag REAL kapitaal in gevaar brengen zonder expliciete shadow deployment + **approval gates**.
   - Fail-closed is de default in alle REAL-paden.
   - **Clarification (2026-07, ADR-0032):** de *gates* blijven verplicht. De *judgment* binnen begrensde lagen (birth/SIM/autonomy) mag geleverd worden door de getrainde **Approval Twin** i.p.v. een permanente menselijke bottleneck. De Twin mag constitution, sandbox, risk shadow aperture of REAL PromotionGate **niet** omzeilen.

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

7. **Geen structurele bypasses in kapitaalpaden** *(no structural bypasses in capital paths)*
   - In `real` en `sim_real_guard` bestaat precies één geautoriseerd pad naar de broker: typed Event Bus + Admission Chain + Final Arbitration + hash-chained `decision_context_id` / `prev_hash`.
   - Structurele bypasses zijn verboden: skip-flags op arbitration/gate, mutable god-state die veiligheid omzeilt, broker-side short-circuits die Final Arbitration overslaan.
   - `lumina_core.risk.aperture_guard` is de permanente regression tripwire; ADR-0010 en de gesloten bypass-inventory (2026-05-31, Phase 1.3.4) zijn bindend.
   - Nood/EOD/force-close en reconciliatie gebruiken **bounded modules** (`EODForceCloseService`, `PaperTradeExecutor`, gatekeeper) — geen parallel trusted path en geen time-boxed bypass (zie ADR-0010).
   - Machine-leesbaar: invariant `no_structural_bypass_capital_paths` in `core/invariants.json`; dagelijkse Guardian static scan (fail-hard).

## Veranderregels

- Wijzigingen aan dit document vereisen:
  - Een expliciete "voor/na" hypothese + falsifieerbare voorspelling.
  - Toepassing van het Recursive Self-Improvement Protocol (inclusief Plan Mode).
  - Een entry in de evolution log die de reden, impact en rollback-pad beschrijft.
  - Sterke aanbeveling voor human review.

Dit document heeft prioriteit boven alle andere project-dna bestanden en alle code.

---

## Evidence Contract (Guardian / enforcement)

Bindende invariants hierboven blijven leidend. Dit blok maakt naleving **measurable** en **falsifiable** via dagelijkse **evidence** — zonder nieuwe invarianten toe te voegen.

**Hypothesis**: Wanneer elke invariant gekoppeld is aan een reproduceerbare Guardian-check en een expliciete **metric**, daalt het risico op stille regressie in REAL-paden.

**Falsifiable predictions**:
| Invariant | Voorspelling (rolling 90d) | Meet-signaal |
|-----------|---------------------------|--------------|
| #1 Kapitaalbehoud | 0 FATAL aperture bypass in strict modes | Aperture Integrity **score** ≥ 9.3 sustained |
| #7 Geen bypass | 0 nieuwe bypass-patronen in capital paths | D5 static scan PASS + `no_structural_bypass_capital_paths` in `invariants.json` |
| #5 Safety vóór evo | Guardian structural health ≥ 9.5 | `dna_health_latest.json` trend |

**Measurable metrics** (dagelijks):
- `aperture_integrity` score (Guardian CAPITAL APERTURE section)
- D5 `capital_aperture_scan.py` exit code (fail-hard)
- Phase 3 gate: `python scripts/phase3_perfection_gate_verify.py` (D2 + Track C chain)

**Evidence / reproduce**:
```bash
python scripts/dna_guardian/validate_dna.py --report --d1-audits --strict-self-score
python scripts/phase3_track_c_gate_verify.py
```

**Rollback**: Verwijder dit Evidence Contract; invariants #1–#7 ongewijzigd. Superseding entry verplicht in `evolution/log/` (Large classificatie voor invariant-wijzigingen; Small voor dit audit-blok).

---

*Laatste update: 2026-07-15 (invariant #1 judgment/Twin clarification per ADR-0032; #2–#7 unchanged; Evidence Contract 2026-06-11)*