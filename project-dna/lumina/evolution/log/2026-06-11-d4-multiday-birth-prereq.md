# 2026-06-11 — D4 multiday birth prereq automation

**Classification**: SIM-only campaign tooling (no capital-path change).

**Hypothesis**: Seeding `state/lumina_birth_completed.flag` when policy zip exists unblocks `run_genuine_d4_campaign.py` without full birth training.

**Prediction (30d)**: `--check-prereqs-only` exits 0 on workspace with policy zip; runtime no longer fails closed on birth guard.

**Rollback**: Delete `lumina_core/audit/d4_birth_prereq.py`; remove flags from `run_genuine_d4_campaign.py`.

## Done

- `lumina_core/audit/d4_birth_prereq.py` — `ensure_birth_prereqs(workspace_root, seed=...)`
- `run_genuine_d4_campaign.py` — `--seed-birth-flag` / `--no-seed-birth-flag` (default seed on), `--check-prereqs-only`
- Tests: `tests/audit/test_d4_birth_prereq.py`

## Verify

```bash
py -3.13 scripts/run_genuine_d4_campaign.py --check-prereqs-only
py -3.13 scripts/run_genuine_d4_campaign.py --duration-min 5 --target-arb-ctxs 3
```
