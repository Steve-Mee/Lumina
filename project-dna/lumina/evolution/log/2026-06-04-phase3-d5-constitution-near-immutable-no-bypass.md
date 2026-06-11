# 2026-06-04 — Phase 3 D5: Near-immutable no-bypass rule (constitution + Guardian fail-hard)

**Classification**: Large (DNA + Guardian enforcement). Advances 05-31 Phase 3 deliverable 5.

**Parents**: D5 plan; ADR-0010; bypass inventory closed (1.3.4); `2026-06-04-phase3-d5-inventory-touchpoints.md`.

## Hypothesis

Codifying "no structural bypasses in capital paths" in `constitution.md` + fatal `invariants.json` entry, plus a daily fail-hard static scan, prevents silent re-introduction of trusted-path erosion better than runtime `aperture_guard` alone.

**Falsifiable (90d)**: Zero Guardian D5 failures on mainline; any bypass attempt caught before merge via CI `validate_dna.py --report`.

## Changes

| Artifact | Change |
|----------|--------|
| `core/constitution.md` | Fundamental invariant #7 |
| `core/invariants.json` | `no_structural_bypass_capital_paths` (fatal) |
| `operating-system/dna-validation-rules.md` | Section 2b D5 enforcement |
| `operating-system/rules/capital-aperture-forbidden-patterns.yaml` | Patterns + allowlist |
| `scripts/dna_guardian/capital_aperture_scan.py` | Scan + alignment |
| `scripts/dna_guardian/validate_dna.py` | D5 report block; fail-hard exit |
| `lumina_core/engine/lumina_engine.pyi` | Removed stale god-flag stub |
| Tests | `tests/dna/test_invariants_d5.py`, `test_capital_aperture_scan.py` |

## Verify

```bash
python -m pytest tests/dna/ -q --tb=short
python scripts/dna_guardian/validate_dna.py --report --d1-audits
```

**Evidence (2026-06-04)**: 6 pytest passed; Guardian exit 0; D5 PASS in aperture report.

## Rollback

Revert constitution/invariants/yaml/scan/validate_dna hooks; restore pyi field if needed; evolution log rollback note.

## Next

D6 Guardian self-score vs aperture contracts; D1 live campaign golden path.
