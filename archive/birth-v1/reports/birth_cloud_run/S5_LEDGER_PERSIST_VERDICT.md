# S5 close_ledger persist verdict

**Ticket:** Flush-before-wipe archive so the full S5 series survives `birth_complete`.
**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** `certified`
**practice_mode:** `False`
**REAL:** none. SIM only. Not Perfect Birth. Not Evolution Proof. Not a new S5 exam.

## Verdict

`LEDGER_PERSIST_SHIPPED`

Every live wipe/cap site from Gate 0 is closed without a floor change. Persist is always implementable.

## Gates

| Field | Value |
|---|---|
| gate 0 | `S5_LEDGER_PERSIST_AUDIT.md` — wipe map + 2000-cap is memory **and** checkpoint field |
| gate 1 | one persist law — append-only JSONL + flush-before-wipe + checkpoint tail allowed |
| archive SSOT | `reports/birth_cloud_run/artifacts/s5_close_ledger.jsonl` |
| sidecar | `s5_close_ledger.sha256` written at flush-on-complete |
| live writer | `lumina_core/birth/s5_close_ledger_archive.py` via `apply_s3_inband_rollout_metrics` |

## Live hooks

| Site | Order |
|---|---|
| `apply_s3_inband_rollout_metrics` | flush new rows, **then** `[-MEMORY_CAP:]` |
| `persist_skill_settlement_fields` | flush remainder, **then** checkpoint tail `[-2000:]` |
| `reset_skill_settlement_if_fresh_stage` | flush remainder, **then** clear memory (resume keeps the tail) |
| `complete_foundation_birth` | flush + sha256, **then** `clear_checkpoint` |
| `complete_certified_birth` | flush + sha256, **then** `clear_checkpoint` |

## Floors (unchanged — grep-identical to PR #14)

S5 50 / edge −0.03 / sharpe −2.0 / dd 25 / equity 50000 / policy 150. MES $5. qty=1. Clip `$500+1 tick`. Envelope on. In-band idle S3–S5. No `S5_IDLE_REGIMES`. No `MAX_PLANT`. No `MAX_TIME_STOP`. No `if synthetic`.

## Honesty

PR #14 exam book n=172 cannot be reconstructed. Mid-stage 122-row tail is gone (`clear_checkpoint`). Tracked `artifacts/lumina_birth_checkpoint.json` is a **996-row phoenix_cycle** book, not the exam tail — not imported. Missing 50 not invented. Persist going forward.

## Tape

No new Birth exam. No `--force`. Receipts stay as PR #14 left them. Same fixture hashes if a later shadow is run: `7e86c2bb1c71d514` / `2466d3f41d60657b`.

## Autonomy

Checkpoint JSON may still keep a 2000-row tail for resume size. Crash-resume intact. Evidence survives complete because the JSONL is not under `state/` and is not deleted by `clear_checkpoint`.
