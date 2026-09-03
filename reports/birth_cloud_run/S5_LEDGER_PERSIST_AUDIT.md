# S5 close_ledger persist audit — Gate 0

**Date:** 2026-09-03
**Engine:** BRO-v2 / `BirthPhaseEngineV2`
**training_mode:** certified
**practice_mode:** False
**REAL:** no
**Base:** `d5b7f7f` (PR #14, Birth milestone closed)

Measured before any persist write. Line numbers are the PR #14 tree.
No invented 172-row book. No floor / fill / reward change.

---

## Law (first principles)

A checkpoint may be small. An exam book may not.
In-memory ring buffer ≠ archive.
`birth_complete` is when the book becomes legally interesting — flush, then you may
clear memory or delete the checkpoint tail.

---

## Wipe / cap / drop map

| # | File:line | What happens | Memory | On-disk checkpoint | Archive (pre-ticket) |
|---|-----------|--------------|--------|--------------------|----------------------|
| 1 | `lumina_core/birth/stage3_inband_ssot.py:235` | `apply_s3_inband_rollout_metrics`: after appending `close_ledger_row(tr)`, assigns `loop.close_ledger = ledger[-2000:]` | **cap 2000** | — | none — prefix dropped from RAM |
| 2 | `lumina_core/birth/stage3_inband_ssot.py:62` | `persist_skill_settlement_fields`: `payload["close_ledger"] = list(raw_ledger[-2000:])` | — | **cap 2000** written into `stage_metrics` | none — checkpoint never holds the prefix |
| 3 | `lumina_core/birth/stage3_inband_ssot.py:163` | `restore_skill_settlement_from_metrics`: `host.close_ledger = list(raw.get("close_ledger") or [])` or `[]` | restore tail or **empty** | reads tailed field | none |
| 4 | `lumina_core/birth/stage3_inband_ssot.py:168-194` | `reset_skill_settlement_if_fresh_stage` | **does not assign/clear `close_ledger` today** | — | leftover prior-stage rows stay in the 2000-cap and can evict S5 |
| 5 | `lumina_core/birth/checkpoint.py:185-190` | `clear_checkpoint`: `path.unlink` on both checkpoint JSON files | — | **deletes** `state/lumina_birth_checkpoint.json` and `state/first_boot_checkpoint.json` | none — this is the PR #14 wipe |
| 6 | `lumina_core/birth/foundation_complete.py:180` | `complete_foundation_birth` calls `clear_checkpoint` after the completion flag | — | **drops the exam tail** on `birth_complete` | none |
| 7 | `lumina_core/birth/certificate_evaluate.py:208` | `complete_certified_birth` calls `clear_checkpoint` | — | same delete | none (proving-ground path) |
| 8 | `lumina_core/birth/checkpoint.py:146-150` | `save_checkpoint` overwrites both checkpoint JSON files (workspace rotate) | — | new JSON has only the current tailed `close_ledger` | previous checkpoint object gone |
| 9 | `lumina_core/birth/engine_graduation.py:293-297` | `_commit_stage_graduation` replaces `_active_stage_metrics` with `fresh_stage_metrics_for_stage` (no `close_ledger` key) | loop object may still hold the list until reset | next persist omits prior-stage ledger unless the loop still has it | none |
| 10 | `lumina_launcher/core/birth_reset.py:80-81` | operator wipe lists `state/lumina_birth_checkpoint.json` and `state/first_boot_checkpoint.json` | — | deletes checkpoint | `reports/birth_cloud_run/artifacts/` is **not** in the wipe list |

No `close_ledger.clear()` anywhere in the tree.
No `close_ledger = []` literal except the restore else-branch (`stage3_inband_ssot.py:163`).

`mark_birth_complete_from_artifacts` (`lumina_core/maturity/maturity_service.py:160`) does **not** touch `close_ledger`.
`is_birth_exit_sufficient` does **not** touch `close_ledger`.

---

## Is the 2000-row cap in-memory only?

**No.** It is both:

1. **In-memory** — `apply_s3_inband_rollout_metrics` `stage3_inband_ssot.py:235`.
2. **On-disk checkpoint field** — `persist_skill_settlement_fields` `stage3_inband_ssot.py:62` writes the same `[-2000:]` into `stage_metrics.close_ledger`, which `save_checkpoint` persists to `state/lumina_birth_checkpoint.json` (and the first-boot alias).

A sibling cap exists for `stage_val_pnl` / `stage_val_r` (`STAGE_VAL_PNL_CHECKPOINT_CAP = 2000` in `stage_loop_progress_metrics.py:15`). That is USD series, not the exam book.

---

## Where `close_ledger_row` is built

`lumina_core/birth/s5_close_ledger_trace.py:13-40` — `close_ledger_row(tr)`.

Live join: `lumina_core/birth/sim_runner.py:704-732` copies `regime` / `pnl` / `close_reason` / `qty` / `gap` / `point_value` / `reward_on_close` onto the trajectory. `apply_s3_inband_rollout_metrics` (`stage3_inband_ssot.py:228-234`) is the only live appender.

Row keys today: `pnl`, `qty`, `cap_usd`, `close_reason`, `gap`, `plant`, `entry_price`, `risk_usd`, `intended_risk_usd`, `trade_r`, `point_value`, `regime`, `reward_on_close`, `cap_hit`.

Trajectory does **not** currently carry `ts_iso` or `bar_index`. Archive must copy them when present and must not invent them.

---

## Current on-disk destinations

| Path | Git | Role |
|------|-----|------|
| `state/lumina_birth_checkpoint.json` | **gitignored** (`state/` + explicit name) | live resume; `stage_metrics.close_ledger` tailed to 2000; **deleted on `birth_complete`** |
| `state/first_boot_checkpoint.json` | gitignored | alias written by `save_checkpoint`; same wipe |
| `reports/birth_cloud_run/workspace/state/lumina_birth_checkpoint.json` | gitignored workspace state | PR #14 live file — **absent** after `clear_checkpoint` |
| `reports/birth_cloud_run/artifacts/lumina_birth_checkpoint.json` | tracked snapshot | **996** rows, `curriculum_stage=stage5_probe_handoff`, `phase=phoenix_cycle`, `stage_trades=996`. This is **not** the 122-of-172 exam tail |
| `reports/birth_cloud_run/artifacts/s5_close_ledger_worst5.json` | tracked | worst-5 only (PR #13 / #14). Not a book |
| `reports/birth_cloud_run/artifacts/s5_instrument_ssot_close_ledger_worst5.json` | tracked | same class |
| `reports/birth_cloud_run/artifacts/s5_close_ledger.jsonl` | (this ticket) | **missing** — no append-only archive existed |

`reports/birth_cloud_run/` is tracked (`!reports/birth_cloud_run/**`). That is why the durable copy must live under `reports/birth_cloud_run/artifacts/`, not under `state/`.

---

## PR #14 evidence honesty

- Exam census: receipt n=172 (`s5_receipt.json`).
- Mid-stage persist named in PR #14 audit: 122 of 172.
- Workspace checkpoint after complete: **gone** (`clear_checkpoint`).
- Tracked artifacts checkpoint: **996 phoenix_cycle rows**, not the 122-row exam tail.
- PR #13 n=1124 full book: never in git (worst-5 only).

**The 172-row S5 exam book cannot be reconstructed. The missing 50 will not be invented. Persist going forward.**

The 996-row phoenix snapshot is a different book (training / recovery, not the certified exam). It is **not** imported into the JSONL.

---

## Live sites this ticket must close

1. Flush new rows in `apply_s3_inband_rollout_metrics` **before** `[-2000:]`.
2. Flush remainder + sha256 sidecar in `complete_foundation_birth` **before** `clear_checkpoint`.
3. Flush remainder in `complete_certified_birth` **before** `clear_checkpoint`.
4. Flush remainder, then clear memory, on fresh `reset_skill_settlement_if_fresh_stage` (resume keeps the tail).
5. Checkpoint JSON may keep `[-2000:]`. Archive must never truncate to 2000.
