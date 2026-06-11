# 2026-06-04 — D2 sub-slice 15: RuntimeMonitoringService

**Classification**: Execution evidence (observability decomp; non-capital path).

**Parents**: `2026-06-04-phase3-d2-completion-roadmap.md`, 05-31 SPF-006, MC D2 Yellow.

## Change

- **New**: `lumina_core/engine/runtime_monitoring_service.py` — `RuntimeMonitoringService.compute_session_kpis()` + `publish_snapshot()`.
- **Thin**: `runtime_workers._compute_session_kpis` / `_publish_runtime_monitoring_snapshot` delegate (compat for `SupervisorPhaseStateMachine` lazy imports).
- **Tests**: `tests/engine/test_runtime_monitoring_service.py` (KPI, snapshot payload, god grep guard).
- **Gate**: `scripts/phase3_perfection_gate_verify.py` extended.

## Verify

```bash
python scripts/phase3_perfection_gate_verify.py
python -c "from pathlib import Path; print(len(Path('lumina_core/runtime_workers.py').read_text().splitlines()), 'lines')"
```

## Remaining on god (honest)

- Twin bootstrap in `_old_supervisor_loop_inner` → **sub16**
- `state_persist_daemon` → **sub17**
- Optional facade → **sub18**

## Rollback

Revert `runtime_monitoring_service.py`, restore inline KPI/snapshot in `runtime_workers.py`.

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

