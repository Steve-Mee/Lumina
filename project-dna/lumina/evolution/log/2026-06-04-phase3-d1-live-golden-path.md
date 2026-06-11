# 2026-06-04 — Phase 3 D1: Live campaign golden path

**Advances**: Phase 3 deliverable 1 (one human, 20 minutes) — genuine D4 ctx integration.

## Changes

- `lumina_core/audit/d1_golden_path.py` — load ctxs from `d4_genuine_campaign_evidence_*.json`, verify build/export contract
- `scripts/phase3_d1_golden_path_verify.py` — CLI gate
- `tests/audit/test_d1_golden_path.py` — 4 tests

## Verify

```bash
python scripts/phase3_d1_golden_path_verify.py
python -m pytest tests/audit/test_d1_golden_path.py -q --tb=short
```

**Evidence**: D1_GOLDEN_PATH_OK, 3/3 verified; manifest in `state/audits/d1_golden_path_verify/`.

## Next

D6 Guardian self-score (Plan Mode contract: `2026-06-04-phase3-d6-guardian-self-score-plan.md`).
