# Birth curriculum stage floors (normative SSOT)

**Status:** Locked / normative — superseded in part by [ADR-0046](adr/0046-birth-foundation-evolvable-plant.md) (2026-08-14)  
**Audience:** Operators, engineers, agents

---

## One-line doctrine (memorize this)

> **Birth = evolvable plant.** Pass is process-R + occupancy + first-touch, never WR 20/35/40.  
> **Stage 1** = closed loop (stops stop: median loss R ≤ 1.5).  
> **Stage 2** = selectivity (occupancy 30–70%).  
> **Stage 3** = mixed body (edge ≥ −5pp vs first-touch).  
> **Stage 4** = viable plant (beat first-touch AND mean R ≥ E_mech−0.10 on validation).  
> **Stage 5** = holdout probe + fitness vector (occupancy 25–75% via `_common_body` is a fail-closed extra vs the probe table).  
> **Profit (WR ≥ BE)** = Playground. **Evolution Proof** = Awakening. **Cert OOS 0.48** = Proving Ground.  
> **Birth exit** = five `foundation_v2` receipts + fitness vector — never artifacts-only.

If a checklist, chat, or older paragraph says Stage 2/3 pass at 35% WR or Stage 5 at 40% WR, **ADR-0046 wins**.

---

## Metric SSOT

`lumina_core/birth/foundation_metrics.py`

```
risk_usd_i    = qty_i * stop_pct_i * entry_i * 5.0
R_i           = pnl_i / risk_usd_i
median_loss_R = median(|R_i| for losses)
p_ft          = first_touch_target_hit_rate
E_mech        = p_ft * net_rr − (1 − p_ft)
edge          = skill_WR − p_ft
occupancy     = flat_bars / total_signals   # never HOLD%
```

`qty` is the contracts on that close. A 1-contract stop denominator with a 8-lot fill is a unit lie. Stage 1 pins qty=1.

Rolling WR and WR−0.50 expectancy are HUD/training pressure only. They cannot set `passed`.

---

## Relocated gates (do not forget)

| Gate | Home |
|------|------|
| Economic viability (mean R ≥ 0, WR ≥ BE) | Playground — `lumina_core/maturity/post_birth_skill_gates.py` |
| Risk Sharpe ≥ 0.20, DD ≤ 12% | Apprenticeship |
| Evolution Proof (OOS 0.45 or +5pp vs fitness vector) | Awakening |
| Certificate OOS 0.48 / Sharpe 0.35 / DD 8% | Proving Ground / cert pipeline |
| Perfect Birth | Phase 2 unlock (not Birth exit) |

---

## Code SSOT

- Pass: `lumina_core/birth/foundation_pass.py` via `evaluate_stage_pass`
- Stages: `ordered_stages()` = five foundation enums
- Exit: `lumina_core/maturity/birth_exit.py`
- Lock tests: `tests/birth/test_foundation_loopholes.py`
