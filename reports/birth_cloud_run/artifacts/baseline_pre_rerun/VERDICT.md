## Verdict
`BIRTH_MILESTONE_OPEN`

## Evidence table
| Criterion | Status | Proof (path or log line) |
| Engine BRO-v2 + sim_runner physics | PASS | `reports/birth_cloud_run/workspace/logs/lumina_full_log.csv` `birth.engine.version=BRO-v2 budget_cap=8000`; S1 receipt `engine_version=BRO-v2`; engine class `BirthPhaseEngineV2` in `run1.log`; physics via `lumina_core/birth/sim_runner.py` (no InfiniteSimulator, no practice toy ticks) |
| Synthetic fixture accepted as history cache | PASS | `data_manifest.reused_manifest=true` in `workspace/state/lumina_birth_progress.json`; `certified_tick_cache_present` true; `01_fixture_manifest.json` |
| ≥3 regimes / holdout present | PASS | holdout_regimes `NEUTRAL, TREND_DOWN, TREND_UP` in fixture manifest and progress `data_manifest` |
| S1 receipt verified | PASS | `reports/birth_cloud_run/s1_receipt.json` schema `foundation_v2`; `verify_stage_pass_receipt(..., training_mode="certified")` → True |
| S2 receipt verified | FAIL | missing; stall `stage2_metric` occupancy 0.903 not in 30–70% |
| S3 receipt verified | FAIL | missing (S2 never passed) |
| S4 receipt verified | FAIL | missing |
| S5 receipt verified | FAIL | missing |
| fitness vector checksum consistent | FAIL | `state/lumina_birth_fitness_vector.json` absent |
| is_birth_exit_sufficient() == True | FAIL | called on workspace → False; missing `foundation_five_receipts_v2` + `foundation_fitness_vector` |
| Crash-resume without human restart | PASS | `reports/birth_cloud_run/run2_resume_evidence.json`: kill mid-S1 at `stage_trades=50` (SIGTERM), resume `force=False` continued S1 then entered S2; `rewound_to_s1=false` |
| Zero REAL / zero Fabric dependency in this run | PASS | `mode: sim`; runner never calls `container.start()`; `LUMINA_FABRIC_SUPERVISOR=0`; no broker connect; workspace isolated under `reports/birth_cloud_run/workspace` |
| Honest labeling of synthetic source | PASS | tick `source=synthetic_cloud_fixture`; `01_fixture_manifest.json` `source=synthetic_cloud_fixture`; `real_data_pct=0.0` (certificate would fail 95% — not a Birth-exit bar) |

## What the organism actually learned
Live Run 1 SSOT also remains at `reports/birth_cloud_run/workspace/state/lumina_birth_progress.json` (gitignored `state/` glob). Git copies: `reports/birth_cloud_run/artifacts/`.

- Engine consumed reused cache: 213,120 ticks, 88 calendar days, NQ SEP26, holdout 43,170 ticks / 3 regimes.
- S1 Closed loop (verified receipt): 150 trades, 57 wins, WR 0.38, median_loss_R 1.022 (≤ 1.5), geometry_net_rr 2.444 (≥ 0.80), settlement ok, constitution 0, edge vs first-touch +0.0004, engine BRO-v2, schema foundation_v2. Occupancy not a S1 gate.
- S2 Selectivity (no receipt): 7,881 stage trades, cumulative 8,031, occupancy 0.903 (need 0.30–0.70), median_loss_R 1.012 on live progress, mean_R 2.047, WR 0.406, edge vs first-touch −0.083, constitution hard violations 0, soft blocks `risk_exceeds_1pct`. Stall: `foundation_fail` occupancy + snapshot `median_loss_r=None` + `replay_cap days=0`. `plateau_evolution_exhausted`.
- S3–S5: not entered. Fitness vector: not written.
- `is_birth_exit_sufficient(workspace) == False`.

Run 2 (fault inject): checkpoint at S1 `stage_trades=50`; SIGTERM; resume continued S1 (did not zero the plant / did not require a human unstick) and advanced into S2. Resume wall 180s → exit 124 as designed.

Pytest birth slice: 1225 passed, 1 skipped (`tests/birth/`, 33.4s). Wiring net only — not milestone evidence.

## Defect map
P0
- BIRTH-CLOUD-001: S2 occupancy stuck ~90% outside 30–70% → no S2 receipt → Birth exit cannot close.

P1
- BIRTH-CLOUD-002: stall snapshot dropped `unique_calendar_days` to 0 and `median_loss_r` to None (progress still had 88 days / 1.012). Spurious replay_cap in the stall string. Occupancy still independently failing.

P2
- BIRTH-CLOUD-003: Telegram credential skip spam in headless logs.
- BIRTH-CLOUD-004: fixture span 88d vs requested 90d (still ≥86 certified floor).

## What is better vs current code (only if evidence)
- `scripts/run_birth_cloud_shadow.py` + `scripts/run_birth_cloud_fault_inject.py`: same `BirthPhaseEngineV2` as the app; no Tauri/NT/`container.start()`.
- `lumina_core/birth/synthetic_cloud_fixture.py`: writes the real jsonl+split+manifest schema (`save_birth_data_cache`), source=`synthetic_cloud_fixture`, 3 enricher regimes in holdout.
- NQ added to `supported_swarm_roots` so `ApplicationContainer` can boot with `NQ SEP26`.
- Empty model catalog no longer crashes `recommended_for`; workspace falls back to repo catalog.
- `LUMINA_FABRIC_SUPERVISOR=0` skips the NT reconnect storm when history is already on disk. Stage floors / `is_birth_exit_sufficient` / cert OOS 0.48 were **not** lowered.

## Next milestone
OPEN. Single next experiment: **move Stage-2 occupancy into 30–70% on this exact fixture** by making the existing occupancy envelope (FORCE_OPEN / FORCE_HOLD / `occupancy_control_flat` in `sim_runner`) actually bite, then re-run `scripts/run_birth_cloud_shadow.py --force` against the cached tape and demand a verified S2 `foundation_v2` receipt. Do not change the 30–70% floor. Do not declare Birth closed on S1 alone.

## Capital / autonomy / experiment impact
- Capital: SIM / certified-shadow only. `prefer_real_data_only=true` against a labeled synthetic cache. No `container.start()`, no live broker, no REAL orders. Fabric supervisor disabled by env for this run.
- Autonomy: crash/resume continued without a human restart (`rewound_to_s1=false`). S2 did **not** self-recover occupancy into band before plateau exhaust.
- Experiment: never treat green unit tests or an S1 receipt as Birth exit. Never skip Fabric by switching `practice_mode` (that would silently retarget training_mode). Never patch occupancy floors to 90% to green a cloud run. The organism can close S1 process-R on this tape in seconds; S2 selectivity is the real plant test and it failed honestly.
