# AWAKENING GRIND AUDIT

**Date:** 2026-09-03T08:03:01Z (shadow) / reports sealed after fixture content-hash check
**Engine:** BRO-v2 evaluate-only grind (`train=False`, zero PPO / optimizer steps)
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`. `practice_mode=False`.
**Start choice:** `full_holdout_replay_frozen` at **bar index 0** (cleanest full-holdout replay). Not resume-from-172.

---

## Preflight

| Check | Result |
|-------|--------|
| Persist writer (PR #15 / P0b) | `lumina_core/birth/s5_close_ledger_archive.py` present; `tests/birth/test_s5_ledger_persist.py` green |
| PR #14 `s5_close_ledger.jsonl` | **0 rows on disk.** Exam book n=172 was never reconstructed. Mid-stage persist 122/172 is gone with `clear_checkpoint`. **Rows not invented.** |
| S1–S5 `foundation_v2` receipts | on disk under `reports/birth_cloud_run/s{1..5}_receipt.json` |
| Fitness vector | `reports/birth_cloud_run/lumina_birth_fitness_vector.json` checksum `707b5ab9d6b9af96` |
| Floors vs PR #14 | grep-identical: `S5_SHARPE_FLOOR=-2.0`, `S5_DD_MAX_PCT=25`, MES $5, clip, qty=1, occupancy bands, `POLICY_EDGE_MIN_TRADES=150` |
| Frozen π* loadable snapshot | **MISSING** |
| Export hook (this ticket) | `lumina_core/birth/foundation_complete.py:161` calls `export_birth_exit_pi_star` **before** `final_birth_polish` |
| Export helper | `lumina_core/birth/birth_exit_policy_export.py:export_birth_exit_pi_star` → `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip` |
| torch / stable_baselines3 on this VM | **absent** — `PPO.load` cannot succeed here even if a zip appeared |
| gitignored zip | `lumina_agents/ppo/*.zip` never in git; workspace zip from PR #14 VM not on this disk |

Honesty: without loadable S5-pass weights the grind cannot grade the plant. Classification is `INCONCLUSIVE`, not a fake `STABLE`. Retraining to manufacture a zip is a failed ticket.

Birth S5 snapshot (untouched): n=172 policy=172 plant=0 occ=0.280 wr=0.395 p_ft=0.320 edge=+0.076 oos_sharpe=-0.943 oos_dd=14.576% of $50k mean_r=-0.089 e_mech=-0.115 realized mean ≈ −$20.7.

---

## Leg A — seed `20260902` (same certified tape)

| Field | Value |
|-------|-------|
| generator | `synthetic_cloud_fixture` |
| reused_manifest | false (tick cache was gitignored / missing; regenerated) |
| ticks_sha16 / bars_sha16 | `7e86c2bb1c71d514` / `2466d3f41d60657b` (**match PR #14**) |
| price_sha16 (content) | `a7eb832491a5f8aa` |
| holdout bars | 43170 |
| holdout regimes | NEUTRAL 33694 / TREND_UP 5148 / TREND_DOWN 4328 (three labels) |
| start | bar 0, `full_holdout_replay_frozen` |
| train / optimizer_steps | False / 0 |
| frozen_loaded | False |
| n / wr / mean $ / sum $ | 0 / n/a / n/a / n/a |
| mean_r / e_mech / sharpe / dd% of $50k | n/a (no closes) |
| edge / plant / FORCE_OPEN / occ | n/a |
| classification | `INCONCLUSIVE` |

JSONL: `reports/birth_cloud_run/artifacts/grind_A_close_ledger.jsonl` — **0 rows** (no invented closes). Birth `s5_close_ledger.jsonl` not truncated (still absent/empty).

---

## Leg B — seed `20260903` (same generator, different seed)

| Field | Value |
|-------|-------|
| generator | `synthetic_cloud_fixture` |
| reused_manifest | false (expected) |
| ticks_sha16 / bars_sha16 | `7e86c2bb1c71d514` / `2466d3f41d60657b` |
| price_sha16 (content) | `bfff3e8f878c6590` (**≠ A**) |
| holdout bars | 43170 |
| holdout regimes | NEUTRAL 33822 / TREND_DOWN 4804 / TREND_UP 4544 (three labels) |
| start | bar 0, `full_holdout_replay_frozen` |
| train / optimizer_steps | False / 0 |
| frozen_loaded | False |
| frozen bytes vs A | n/a (no zip); would have been the same path/bytes if loadable |
| classification | `INCONCLUSIVE` |

**Fingerprint collision (honest):** `compute_ticks_fingerprint` hashes `len + first_ts + last_ts`, not prices. Seed `20260903` keeps the same calendar, so sha16 collides with seed `20260902` while **price_sha16 and regime_counts differ**. Envelope / ATR / regimes were not quieted.

JSONL: `reports/birth_cloud_run/artifacts/grind_B_close_ledger.jsonl` — **0 rows**.

---

## ADR-0026 Evolution Proof (computed, not stamped)

Birth-exit WR = **0.395349** (S5 receipt). Longer of A/B n = **0**.

`evaluate_evolution_proof` reasons:

- `holdout_trades 0 < min 500`
- `insufficient lift -39.5% (need 5.0% or OOS >= 45.0%)`

`passed_inequalities=False`. **Proof stamped: no.** `state/lumina_evolution_proof.json` not written (`passed=True` is forbidden on INCONCLUSIVE). Missing evidence = fail-closed.

---

## Classifier bounds used (ticket, not new Birth floors)

`STABLE` iff n≥500 (or holdout exhausted with n≥172) AND sharpe > −2.0 AND dd% ≤ 25 AND mean $ > −62 AND sharpe > −3.0.
`GRIND_REGRESS` iff sharpe ≤ −3.0 OR dd% > 25 OR mean $ ≤ −62 OR full-series dd > 50% of $50k.
`INCONCLUSIVE` iff n<172 **or frozen weights cannot be loaded**.

Neither A nor B left the INCONCLUSIVE gate. Remainder fail-closed.

---

## Birth / REAL

- Birth receipts S1–S5 + fitness: **untouched** (PR #14).
- `is_birth_exit_sufficient`: **True** as PR #14 left it (`exit_snapshot.json`). This ticket does not flip it.
- REAL: **no**. Certificate 0.48 / PromotionGate: out of scope.
