# AWAKENING GRIND AUDIT

**Date:** 2026-09-03T08:48:31.991264+00:00
**Engine:** BRO-v2 evaluate-only grind (`train=False`, zero PPO / optimizer steps)
**Capital:** SIM / certified-shadow. REAL=no. NT=no. `LUMINA_FABRIC_SUPERVISOR=0`. `practice_mode=False`.
**Start choice:** `full_holdout_replay_frozen` at **bar index 0**.

GATE 0 closed the PR #16 loopholes (no `lumina_agents/ppo/*.zip` fallback; complete cannot succeed without the zip).
GATE 1 harvested a loadable pre-polish zip. GATE 2 is this evaluate-only rerun.

---

## Preflight

{
  "persist_writer": "lumina_core/birth/s5_close_ledger_archive.py",
  "s5_close_ledger_jsonl_rows": 0,
  "s5_close_ledger_honesty": "PR #14 book not reconstructed; missing rows not invented",
  "s1_s5_receipts_on_disk": true,
  "fitness_vector_on_disk": true,
  "floors_pr14": true,
  "export_site": "lumina_core/birth/foundation_complete.py:export_birth_exit_pi_star",
  "export_call": "lumina_core/birth/foundation_complete.py:134 (before fitness + polish)",
  "frozen_path": "/workspace/reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip",
  "frozen_sha256": "8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03",
  "frozen_loaded": true,
  "s5_n": 172,
  "s5_wr": 0.395349,
  "s5_mean_r": -0.0887405145105915,
  "practice_mode": false,
  "supervisor": "0",
  "gitignored_ppo_used": false
}

Birth S5 snapshot (untouched): n=172 policy=172 plant=0 occ=0.280 wr=0.395 p_ft=0.320 edge=+0.076 oos_sharpe=-0.943 oos_dd=14.576% of $50k mean_r=-0.089 e_mech=-0.115 realized mean ≈ −$20.7.

---

## Frozen π*

- export site: `lumina_core/birth/foundation_complete.py:export_birth_exit_pi_star`
- loadable path: `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`
- sha256: `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03`
- bytes: 202268
- source: `harvest_s5_pass_pre_polish` (isolated certified Birth; not post-polish `lumina_agents/ppo/*.zip`)
- loaded: `True`
- `PPO.load` obs 43-dim / action 4-dim
- post-polish PPO sha16 `6fafc5f0e3128416` — different bytes, refused as π*

---

## Leg A (seed 20260902)

n=218 wr=0.34 mean$=-74.73 sum$=-16290.87 mean_r=-0.299 e_mech=-0.131 sharpe=-4.783 dd=33.982% of $50k edge=+0.014 plant=68 FORCE_OPEN=165 occ=0.757 exits stop=149 target=50 time_stop=19 flatten=0 unknown=0 target∧¬gap=50 cap_hit_frac=0.078 p_ft=0.326 realized_r=-0.299.

ticks_sha16/bars_sha16 `7e86c2bb1c71d514` / `2466d3f41d60657b` (PR #14 match). holdout_exhausted=true. frozen_loaded=true. train=false. optimizer_steps=0. start bar 0.

JSONL: `reports/birth_cloud_run/artifacts/grind_A_close_ledger.jsonl` — **218 rows**. Birth `s5_close_ledger.jsonl` not truncated.

**classification:** `GRIND_REGRESS` because sharpe ≤ −3.0 **and** dd% > 25 **and** mean $ ≤ −62.

---

## Leg B (seed 20260903)

n=171 wr=0.28 mean$=-44.32 sum$=-7578.18 mean_r=-0.337 e_mech=-0.126 sharpe=-3.865 dd=15.343% of $50k edge=-0.046 plant=21 FORCE_OPEN=56 occ=0.759 exits stop=117 target=31 time_stop=23 flatten=0 unknown=0 target∧¬gap=31 cap_hit_frac=0.035 p_ft=0.326 realized_r=-0.337.

same frozen bytes as A. holdout_exhausted=true. train=false. optimizer_steps=0.

**Fingerprint collision (honest):** `compute_ticks_fingerprint` hashes `len + first_ts + last_ts`, not prices. Seed `20260903` keeps the same calendar, so sha16 collides with seed `20260902`. Envelope / ATR / regimes were not quieted.

JSONL: `reports/birth_cloud_run/artifacts/grind_B_close_ledger.jsonl` — **171 rows**.

**classification:** `INCONCLUSIVE` because n=171 < 172.

---

## ADR-0026 Evolution Proof (computed, not stamped)

Birth-exit WR = **0.395349** (S5 receipt). Longer of A/B n = **218**.

`evaluate_evolution_proof` reasons:

- `insufficient lift -5.5% (need 5.0% or OOS >= 45.0%)`

`passed_inequalities=False`. **Proof stamped: no.** `state/lumina_evolution_proof.json` not written (`passed=True` is forbidden on REGRESS).

---

## Classifier bounds used (ticket, not new Birth floors)

`STABLE` iff n≥500 (or holdout exhausted with n≥172) AND sharpe > −2.0 AND dd% ≤ 25 AND mean $ > −62 AND sharpe > −3.0.
`GRIND_REGRESS` iff sharpe ≤ −3.0 OR dd% > 25 OR mean $ ≤ −62 OR full-series dd > 50% of $50k.
`INCONCLUSIVE` iff n<172 **or frozen weights cannot be loaded**.

---

## Birth / REAL

- Birth receipts S1–S5 + fitness: **untouched** (PR #14). Checksum `707b5ab9d6b9af96`.
- `is_birth_exit_sufficient`: **True** as PR #14 left it. This ticket does not flip it.
- REAL: **no**. Certificate 0.48 / PromotionGate: out of scope.
