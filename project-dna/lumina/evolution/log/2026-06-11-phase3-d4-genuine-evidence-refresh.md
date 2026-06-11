# 2026-06-11 — D4 genuine evidence refresh (campaign interim)

**Classification**: Controlled genuine D4 run (paper/production gate paths only).

**Hypothesis**: Refreshing the genuine D4 bundle keeps Guardian D3/D4 forcing current without daemon multiday cost.

**Prediction (30d)**: D1 golden path verify remains green on latest `d4_genuine_campaign_evidence_*.json`.

**Rollback**: Remove `state/audits/genuine_d4_campaign_20260611_182020/` and timestamped bundle files.

## Results

```bash
py -3.13 scripts/phase3_d4_genuine_evidence.py --num-proposals 25 --unsafe 8
# 8/8 unsafe CAUGHT (100%), 0 reached broker
# Bundle: state/audits/d4_genuine_campaign_evidence_20260611_182022.md
```
