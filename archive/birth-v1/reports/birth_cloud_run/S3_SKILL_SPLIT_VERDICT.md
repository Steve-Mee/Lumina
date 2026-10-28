## S3 skill-split verdict
`BIRTH_MILESTONE_OPEN` — exam IMU split landed. S3 receipt not produced this session.

| Field | Value |
|---|---|
| engine | BRO-v2 / BirthPhaseEngineV2 |
| training_mode | certified (`practice_mode=False`) |
| floors | S3 0.25–0.75, `S3_MIN_TRADES=400`, `S3_EDGE_MIN=-0.05`, `POLICY_EDGE_MIN_TRADES=150` unchanged. S2 0.30–0.70 unchanged. Stop cap ≤ 1%. |
| volume IMU | `stage_trades` (total settled stage closes = policy + plant) |
| skill IMU | `stage_policy_trades` / `stage_policy_wins` |
| S2 receipt still verified | **True** (`reports/birth_cloud_run/s2_receipt.json`, `verify_stage_pass_receipt(..., training_mode="certified")` → `ok`; trades=815, policy_trades=253, occupancy=0.604) |
| S3 stage_trades | not measured live this session (no S3 checkpoint on this VM) |
| S3 policy_trades / plant_trades | not measured live this session |
| S3 occupancy | not measured live this session |
| S3 skill_wr / p_ft / edge | replica: policy=0, p_ft=0.338 → `edge=None` + `policy_sample 0 < 150` (not `edge=-0.338`) |
| pass_reason | replica: `foundation_fail:policy_sample 0 < 150 settle=ok` (volume 729 does **not** emit `trades 0 < 400`) |
| S3 receipt path | MISSING |
| verify_stage_pass_receipt certified | S2 True; S3 N/A (no receipt) |
| is_birth_exit_sufficient | **False** (S3–S5 receipts + fitness absent) |

## Law
- `FoundationSnapshot` carries `trades/wins` (plant clock) and `skill_trades/skill_wins` (pilot clock).
- `edge = skill_wr - p_ft` only when `skill_trades >= 150` and `p_ft` is present. Thin sample → `edge is None`.
- `evaluate_foundation_pass` S3/S4/S5 emits `policy_sample n < 150` **before** any `edge=...` / `edge=None < floor` branch.
- S1/S2: no policy_sample, no edge gate. S2 min-trades uses volume. S2 occupancy remains cumulative plant-flat (`occupancy_control_over` untouched).
- HUD maps `policy_sample` to metric `policy_sample`, not `edge`.

## Tests
- `tests/birth/test_s3_snapshot_skill_split.py`: A–G (cloud replica 729/0/0.338, honest edge fail, honest edge pass, snapshot clocks, S2 non-regression, S1 unchanged, HUD mapping).
- `pytest tests/birth/ -q --timeout=60`: **1239 passed, 3 skipped**.
- ruff / mypy --strict / pyright: clean on touched modules.

## Shadow
Not run to an S3 plant. This VM has no S3 checkpoint (`reports/birth_cloud_run/workspace/state/` cache missing). `--force` on `scripts/run_birth_cloud_shadow.py` reconstructed the certified fixture (`source=synthetic_cloud_fixture`, 213,120 ticks, seed hashes `7e86c2bb1c71d514` / `2466d3f41d60657b`) and constructed `BirthPhaseEngineV2`, then aborted at PPO create: `ModuleNotFoundError: No module named 'stable_baselines3'` (torch also absent). That is an environment gap, not an IMU loophole.

Tests-only is therefore the evidence for this ticket. Replica numbers prove the frozen S3 lie (`trades 0 < 400` + `edge=-0.338`) cannot appear.

## Birth status
OPEN. Do not promote S1+S2 receipts to Birth exit. Next live S3 exam must report either a verified S3 `foundation_v2` receipt or an honest fail with `policy_trades>=150` and a real edge number.

## Capital / autonomy
SIM / certified-shadow only. No REAL, no `container.start()`, `LUMINA_FABRIC_SUPERVISOR=0`. Crash-resume path untouched. Pass eval reads caller live `trades` / `policy_trades` (no warmup freeze as exam).
