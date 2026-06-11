# 2026-06-11 — Campaign daily driver + parent hypothesis draft

**Classification**: Campaign tooling (read-only measurement).

**Hypothesis**: A single daily script increases adherence to ninety-day append discipline vs ad-hoc commands.

**Prediction (30d)**: Daily `phase3_campaign_daily.py` produces monotonic growth in `phase3_ninety_day_gate_snapshots.jsonl`.

**Rollback**: Delete `scripts/phase3_campaign_daily.py`.

## Implemented

- `scripts/phase3_campaign_daily.py` — `--refresh --append` + protocol adherence; optional `--gate` weekly
- Draft: `2026-08-29-phase3-parent-hypothesis-draft.md` (human sign-off 2026-08-29)

## Multiday D4 note

`run_genuine_d4_campaign.py` requires first-boot artifacts (`lumina_birth_completed.flag`) in isolated state; not run this session. Controlled D4 refresh already green (8/8 catch).

## Verify

```bash
py -3.13 scripts/phase3_campaign_daily.py
```
