# Lumina Birth Adaptive Wall Retry — Implementatieplan

**Status:** Goedgekeurd — implementatie gestart 2026-06-25  
**Spec:** [LUMINA_BIRTH_ADAPTIVE_WALL_RETRY_DESIGN.md](LUMINA_BIRTH_ADAPTIVE_WALL_RETRY_DESIGN.md) v2.1

## Doel

Automatische intelligent recovery bij birth stage stalls na volume gate: verhoog exploration (`chunk_target`), log beslissing, restart stage vanuit checkpoint. Max retries. `wall_behavior="strict"` schakelt uit.

## Fasen

| Fase | Scope | Bestanden |
|------|-------|-----------|
| 0 | Tracking setup | `docs/plan.md`, `docs/progress.md`, `TODO.md` |
| 1 | Config | `lumina_core/birth/config.py` |
| 2 | Engine core | `lumina_core/birth/engine.py` |
| 3 | HUD | `lumina_core/birth/stage_scorecard.py` |
| 4 | Tests | `tests/birth/test_adaptation_decision.py` + bestaande tests |
| 5 | Handoff | `docs/progress.md` summary |

## Key Decisions

1. **`continue` in bestaande loop** — geen recursieve `_run_stage_research_loop`
2. **Soft reset bij adaptatie** — reset attempt/stagnation/wall-timer; behoud stage metrics + policy
3. **Checkpoint via `stage_metrics`** — geen checkpoint v4 bump
4. **Tijdelijke `rollout_chunk_trades` override** bij adaptatie
5. **`_get_adaptation_decision` module-level** in engine.py
6. **`calculate_simple_slope`** in stage_scorecard.py

## Stall intercept punten

- `_certified_stage_stall_result` stagnation+wall path (~1578)
- Force stall bij max rollouts (~1700)

Zie volledig plan in `.cursor/plans/adaptive_wall_retry_d8f8ee60.plan.md` (niet bewerken).
