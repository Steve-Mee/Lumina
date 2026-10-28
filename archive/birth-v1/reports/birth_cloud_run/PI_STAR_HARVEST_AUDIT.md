# π* HARVEST AUDIT

**Date:** 2026-09-03T08:43:00.845802+00:00
**Engine:** isolated certified Birth → export before polish → seal to grind path
**Capital:** SIM / certified-shadow. REAL=no.

{
  "schema": "pi_star_harvest_v1",
  "timestamp": "2026-09-03T08:43:00.845802+00:00",
  "birth_exit_code": 0,
  "harvested_path": "/workspace/reports/pi_star_harvest/workspace/reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip",
  "harvested_exists": true,
  "canonical_path": "/workspace/reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip",
  "canonical_exists": true,
  "canonical_bytes": 202268,
  "used_gitignored_ppo": false,
  "pr14_before": {
    "s5_exists": true,
    "fitness_exists": true,
    "s5_trades": 172,
    "fitness_checksum": "707b5ab9d6b9af96",
    "pr14_checksum_intact": true
  },
  "pr14_after": {
    "s5_exists": true,
    "fitness_exists": true,
    "s5_trades": 172,
    "fitness_checksum": "707b5ab9d6b9af96",
    "pr14_checksum_intact": true
  },
  "pr14_untouched": true
}

PR #14 `s5_receipt.json` / fitness checksum `707b5ab9d6b9af96` were not rewritten.
Grind load path is only `reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip`.

## Freeze identity

- Pre-polish π* sha256: `8cc435c68a37b0a070e38bccc4bfd402d4a802396bd7cd2fcce02f50acf69a03` (202268 bytes)
- Isolated harvest post-polish `lumina_agents/ppo/lumina_ppo_policy.zip` sha16 `6fafc5f0e3128416` — **different bytes**. Not used.
- `PPO.load` succeeds: obs Box 43-dim, action Box 4-dim, `num_timesteps=1536`
- PR #14 weight files were gone (gitignored). This zip is a **new certified S5-pass freeze** of the same airframe (same floors, same MES $5 physics, isolated workspace). It is not reconstructed PR #14 bytes.
- Harvest Birth complete: cumulative trades 1123, five stages passed, then export **before** polish.
