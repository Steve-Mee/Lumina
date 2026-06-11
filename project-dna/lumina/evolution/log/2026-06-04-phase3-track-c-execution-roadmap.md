# 2026-06-04 — Phase 3 Track C Execution Roadmap (post D2 close-out)

**Classification**: Planning + execution contract. D2 Track A+B complete per `2026-06-04-phase3-d2-runtime-workers-closeout.md`.

**Track C close-out (2026-06-04)**: `2026-06-04-phase3-track-c-closeout.md` — gate `python scripts/phase3_track_c_gate_verify.py`.

**Immutable parents**: 05-31 analysis + 90-day roadmap + `aperture-hardening-mission-control.md`.

---

## Priority order (after D2)

| Order | Deliverable | Status | Next action |
|-------|-------------|--------|-------------|
| 1 | **D3** Guardian aperture forcing | **Green-Yellow** | Slice C1 + daily forcing stack (close-out) |
| 2 | **D1** One-human 20 min audit | **Green-Yellow** | Golden path on genuine D4 evidence |
| 3 | **D5** Constitution near-immutable bypass | **Green-Yellow** | Fail-hard `capital_aperture_scan.py` |
| 4 | **D6** Guardian self-scores aperture | **Green-Yellow** | `--strict-self-score` + `dna_health_latest` v2 |
| 5 | **D4** 30-day SIM demo | Green-Yellow | Optional longer external runs |

---

## D3 Slice C1 (executed 2026-06-04)

- `merge_d1_audit_context_ids()` in `aperture_audit_artifact.py`
- Guardian: merge Final Arbitration ctxs from logs before D1 auto-audit
- Guardian: `Phase 3 D3 FORCING` block when broken chains, missing fill lineage, or no D1 ctx pool

**Verify**:

```bash
python -m pytest tests/audit/test_aperture_audit_artifact.py -q --tb=short
python scripts/dna_guardian/validate_dna.py --report --d1-audits
```

---

## D5 plan (Plan Mode — do not implement without approval)

**Goal (05-31 verbatim)**: Update `constitution.md` and `invariants.json` so "no structural bypasses in capital paths" is near-immutable.

**Proposed slices** (execution session after human sign-off):

1. **D5.1** — Inventory all constitution/invariant touch points + aperture_guard coupling
2. **D5.2** — Add invariant keys + Guardian check that fails on new bypass patterns in capital paths
3. **D5.3** — Document emergency override as single auditable time-boxed path (if retained)
4. **D5.4** — Evolution log + MC Green only after Guardian enforces + tests

**Risks**: False positives on research paths; requires explicit REAL vs SIM boundaries.

**Rollback**: Revert invariant + Guardian check; keep aperture.yaml static scan.

---

## D6 sketch (after D3)

Guardian compares its own report sections against aperture contract schemas; scores self-consistency; surfaces drift in MC.

---

## Checklist

- [x] D3 slice C1 (merge + forcing violations)
- [x] D1 live campaign artifact golden path (`2026-06-04-phase3-d1-live-golden-path.md`)
- [x] D5 approved plan → implementation (`2026-06-04-phase3-d5-constitution-near-immutable-no-bypass.md`)
- [x] D6 (`2026-06-04-phase3-d6-guardian-self-score.md`)
- [x] Track C unified gate + MC/agent-context close-out (`2026-06-04-phase3-track-c-closeout.md`)

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

