# S2 certified-shadow rerun verdict

`S2_PASS_BIRTH_OPEN` — IMU+ATR already on `main` moved Stage-2 cumulative plant-flat into `[0.30, 0.70]` and produced a verified `foundation_v2` S2 receipt on the same-class tape. Birth is **not** closed (S3–S5 + fitness missing).

| Field | Value |
|---|---|
| branch / commit | `cursor/s2-occupancy-rerun-7a1c` @ this docs commit; IMU law from `origin/main` `1eba46d95c4d2ef24984d0783287566f82952e54` (already merged) |
| occupancy_control_over present | yes — `lumina_core/birth/stage2_participation_envelope.py:82` (helper) and `:191` (`over_flat = occupancy_control_over(...)`) |
| tape | **regenerated** (workspace tick cache gitignored / missing on this VM) with `CloudFixtureSpec()` defaults: `seed=20260902`, `calendar_days=90` (actual **88**), NQ SEP26, 213,120 ticks, holdout regimes `TREND_UP` / `TREND_DOWN` / `NEUTRAL`. Hashes **identical** to first run: `hash=7e86c2bb1c71d514` `raw_ticks_hash=2466d3f41d60657b`. `source=synthetic_cloud_fixture`, `real_data_pct=0.0`, `reused_manifest=true` after write. |
| S1 receipt | **pass** — `foundation_v2`, 150 trades, WR 0.40, `median_loss_r=1.023` ≤ 1.5, constitution hard 0, `verify_stage_pass_receipt(..., training_mode="certified")` → **True** (`ok`) |
| S2 occupancy cumulative | **0.655280** (receipt `occupancy` / `range_flat_ratio=0.65528`) — baseline **0.903** |
| S2 occupancy rolling | last S2-live `occupancy_control_flat=0.542` at 1000/1050 stage trades (both IMUs in-band at pass). Mid-S2 rolling dipped to 0.324 while cumulative stayed 0.636 |
| participation_force_open/hold/flat/exit/passthrough | last S2-live (1000 trades): **open=4368 / hold=3937 / flat=1427 / exit=9 / passthrough=null** (field not in progress SSOT). Implied passthrough ≈ `51056 − (4368+3937+1427+9) = 41315` using receipt `range_total_signals` |
| median bars-in-trade S2 | median not in SSOT. Mean in-market bars/trade ≈ **16.76** = `(1−0.65528)×51056/1050`. `closes_flatten=0`, `closes_stop=728`, `closes_time_stop=9` |
| S2 receipt verified certified | **True** (`reason=ok`) — `reports/birth_cloud_run/s2_receipt.json` + `artifacts/s2_receipt.json` |
| S3–S5 | **S3 entered**, no S3 receipt. S4/S5 not entered. Fitness vector **absent** |
| fitness vector | **absent** (`evaluate_birth_exit` missing `foundation_fitness_vector` + `foundation_five_receipts_v2`) |
| is_birth_exit_sufficient | **False** |
| stall reason | **none on S2**. S3 still running at verdict freeze (~702 stage trades, elapsed ~1384s): live `terminal_stall_reason=None`; foundation blockers remain `trades 0 < 400` (snapshot trades stuck at 0) **and** `edge=-0.338 < -0.05`. Occupancy S3 ~0.576 in `[0.25, 0.75]` |
| follow-up applied | **none** this session (Gate B passed). ATR FORCE_OPEN stop (`force_open_stop_from_atr`) was already on this `main` from the prior IMU agent — not re-implemented |
| verdict | **S2_PASS_BIRTH_OPEN** |

## Gate A — IMU is live

- Helper: `occupancy_control_over(cumulative_flat=0.90, rolling_flat=0.50) == 0.90`.
- `decide_stage2_participation(..., range_flat_ratio=0.90, rolling_flat_ratio=0.50, position=0)` → `FORCE_OPEN` / `over_flat_force_open`.
- Docstring does **not** say FORCE_OPEN is rolling-only; it states `max(rolling, cumulative)`.
- This rerun never sat at cumulative flat > 0.72 in the monitor (first S2 snapshot already **0.636** at 300 trades with `participation_force_open=1514`). FORCE_OPEN kept incrementing through S2 (1514 → 4368) while cumulative stayed in-band. Wiring to `sim_runner` is live; the plant pulled the exam into band immediately.

## Gate B — S2 plant (this ticket)

ALL required:

| Check | Result |
|---|---|
| `foundation_v2` S2 receipt written | yes — 1050 trades, 316 wins, `passed_at=2026-09-02T13:17:24Z` |
| `verify_stage_pass_receipt(..., training_mode="certified")` | **True** / `ok` |
| cumulative occupancy/flat in `[0.30, 0.70]` | **0.655280** (baseline 0.903) |
| process-R honest | `median_loss_r=1.055` ≤ 1.5; constitution **hard** violations **0**; `unique_calendar_days=88` |
| floors unchanged | `S2_OCCUPANCY_MIN/MAX=0.30/0.70`, `S3=0.25/0.75`, `BIRTH_MAX_RISK_STOP_PCT=0.01` in `lumina_core/birth/foundation_metrics.py` + constitution guard |

Soft blocks `risk_exceeds_1pct` still fire (same class as the first run). Hard path stayed 0. Stops remain clipped ≤ 1%.

## Gate C — Birth milestone

Not reached. S1+S2 receipts only. S3 occupancy is already in-band (~0.576) but the S3 exam is blocked by frozen first-touch edge (−0.338 vs floor −0.05) and a foundation snapshot that still reports `trades=0` after 579+ live stage trades. That is the **next** P0, not an S2 loophole.

## Run identity

- Engine: `BirthPhaseEngineV2` / BRO-v2 via `scripts/run_birth_cloud_shadow.py --force --timeout-sec 5400`
- `practice_mode=False`, `training_mode=certified`, `LUMINA_FABRIC_SUPERVISOR=0`, no `container.start()`, no REAL / Fabric / NT
- Target trades 8000 (CPU; `torch.cuda.is_available()=False`)
- Infra note: this VM image lacked `torch` / `stable_baselines3`; installed `torch==2.11.0` + `stable_baselines3==2.8.0` into `.venv` before the plant (not a floor change)

## Baseline lock

| | Previous S2 (VERDICT.md) | This rerun |
|---|---|---|
| occupancy | 0.903 | **0.655** |
| stage trades at stop | 7,881 (no receipt) | **1,050** (verified receipt) |
| S2 receipt certified | missing | **True** |

## Artifacts

Copied under `reports/birth_cloud_run/artifacts/` because `state/` is gitignored:

- `s1_receipt.json`, `s2_receipt.json`
- `lumina_birth_progress.json`, `lumina_birth_checkpoint.json`, `lumina_birth_cache_manifest.json`

Live SSOT remains `reports/birth_cloud_run/workspace/state/`. Monitor: `s2_rerun_monitor.jsonl`. Engine log: `s2_rerun.log`.

## Capital / autonomy / experiment

- Capital: SIM / certified-shadow only. Stops ≤ 1%. No REAL.
- Autonomy: envelope + existing ATR plant pulled cumulative flat from the 0.903 class of failure into 0.655 without a human occupancy patch.
- Experiment: same generator, same hashes, IMU on main, binary S2 receipt first. No floor widening. Birth remains open until S3–S5 + fitness.
