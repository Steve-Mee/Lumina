# 2026-06-04 — Phase 3 D6: Guardian self-score vs aperture contracts

**Advances**: 05-31 Phase 3 deliverable 6.

## Changes

- `operating-system/rules/guardian-self-score-contract.yaml` — dimensions + thresholds
- `scripts/dna_guardian/guardian_self_score.py` — panel collection + heuristic score
- `validate_dna.py` — enrich report; D6 print section; `--strict-self-score` (fail exit if < 6)
- `tests/dna/test_guardian_self_score.py`

## Dimensions (weighted)

structural_dna, aperture_integrity, d5_no_bypass, d3_forcing, d4_genuine_surface, d1_ctx_pool

## Verify

```bash
python -m pytest tests/dna/test_guardian_self_score.py -q --tb=short
python scripts/dna_guardian/validate_dna.py --report --d1-audits
python scripts/dna_guardian/validate_dna.py --report --strict-self-score
```

## Notes

- v1 heuristic only (no LLM). Warn below 8.0; strict mode fails below 6.0.
- `phase3_aperture_panel` attached to JSON report for machine consumers.
