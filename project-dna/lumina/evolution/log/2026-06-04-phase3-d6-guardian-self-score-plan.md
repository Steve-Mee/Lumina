# 2026-06-04 — Phase 3 D6 Plan (Guardian self-score vs aperture contracts)

**Classification**: Planning artifact — execute in a future session after D1 golden path.

**Parent**: 05-31 deliverable 6; Track C roadmap.

## Goal

DNA Guardian scores its own daily report sections against aperture contracts (D3/D5/D1 presence, consistency, no contradictions).

## Proposed slices (D6.1–D6.4)

1. **D6.1** — Define `guardian_self_score_contract.yaml` (required report sections + JSON report fields)
2. **D6.2** — `scripts/dna_guardian/guardian_self_score.py` — parse last report / in-memory report dict, emit 0–10 subscores
3. **D6.3** — Embed in `validate_dna.py` (warn if < 8, fail if < 6 when `--strict-self-score`)
4. **D6.4** — Tests + MC D6 Green-Yellow

## Non-goals

- LLM scoring (heuristic/structural only for v1)
- Changing trading or risk code

## Entry criteria

- D5 fail-hard green
- D1 golden path script green

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

