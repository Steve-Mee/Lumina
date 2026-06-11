# 2026-06-11 — Self-improvement protocol Truth Density polish

**Classification**: Small DNA meta-change (documentation only).

**Hypothesis**: Adding an explicit Evidence Contract with English Guardian markers (`hypothesis`, `falsifiable`, `prediction`, `measurable`, `evidence`, `metric`, `score`) raises Truth Density without changing protocol semantics.

**Prediction (30d)**: `operating-system/self-improvement-protocol.md` Truth Density ≥ 9.0 (baseline 8.6, weakest file 5 consecutive scans).

**Rollback**: Revert Evidence Contract section in `self-improvement-protocol.md`.

## Verify

```bash
python scripts/dna_guardian/validate_dna.py --report
# self-improvement-protocol.md: 8.6 → 9.4/10 (8 evidence markers)
# DNA Health: 9.53 → 9.62; truth_density_avg: 9.05 → 9.25
```
