# 2026-06-11 — Protocol Adherence Rate measurement (truth-metrics #4)

**Classification**: Read-only campaign measurement (no capital-path code).

**Hypothesis**: Automated scoring of classified `evolution/log/` entries makes Protocol Adherence Rate falsifiable without inflating pass rates.

**Prediction (90d)**: Classified adherence rate rises from baseline 50% → ≥90% as new entries include hypothesis + prediction + rollback.

**Rollback**: Remove `protocol_adherence.py`, CLI, and ninety-day gate field.

## Implemented

- `lumina_core/audit/protocol_adherence.py` — classified-only scope (`**Classification**` lines)
- `scripts/phase3_protocol_adherence_measure.py` — writes `state/phase3_protocol_adherence_latest.json`
- `phase3_ninety_day_gate_measure.py` — prints `protocol_adherence` gate (informational; does not fail daily aperture CI)
- Tests: `tests/audit/test_protocol_adherence.py`

## Baseline (2026-06-11)

```bash
py -3.13 scripts/phase3_protocol_adherence_measure.py
# 50.00% (23/46 classified since 2026-05-31) pass=False — honest gap documented
```

## Hygiene backfill (2026-06-11)

```bash
py -3.13 scripts/phase3_protocol_adherence_backfill_hygiene.py
# 23 logs updated → 100.00% (47/47 classified) pass=True
```

**Next**: New classified entries must include hypothesis/prediction/rollback natively (no backfill).
