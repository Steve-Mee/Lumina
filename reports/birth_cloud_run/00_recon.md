# Birth Cloud Shadow — Phase 0 Recon

**Task class:** Safety-Critical (SIM / certified-shadow only).  
**Date:** 2026-09-02  
**Engine SSOT:** `BirthPhaseEngineV2` (`lumina_core/birth/engine.py`). Thin façade `lumina_core/lumina_birth_engine.py` is **deleted**; launcher aliases `BirthPhaseEngineV2 as LuminaBirthEngine`.

## 1. Engine identity

- Version constant: `BRO_ENGINE_VERSION = "BRO-v2"` in `lumina_core/birth/config_curriculum.py:12`.
- Logged at bootstrap: `birth.engine.version=%s` in `lumina_core/birth/birth_phase_bootstrap.py:97-103`.
- `run_birth_phase` on the engine delegates to `lumina_core/birth/birth_phase_orchestrator.py:34-70`.
- Training physics: `lumina_core/birth/sim_runner.py` (`RLTradingEnvironment` + `ValuationEngine`, ADR-0012). `InfiniteSimulator` is not on this path.

## 2. On-disk certified tick cache (do not invent a parallel format)

| File | Path helper | Role |
|------|-------------|------|
| Tick tape | `state/lumina_birth_ticks_cache.jsonl` | One JSON object per tick (`tick_cache_persist.py:18-19`) |
| Purged split | `state/lumina_birth_split_cache.json` | `train` / `holdout` lists + `holdout_pct` (`tick_cache_persist.py:22-88`) |
| Manifest | `state/lumina_birth_cache_manifest.json` | `cache_schema_version=1`, hashes, days, instruments (`tick_cache_persist.py:26-147`) |

Tick row schema after `normalize_tick_rows` (`history_loader.py:94-124`):

```
timestamp, last, close, bid, ask, volume, regime, imbalance, source
```

Enrichment (`tick_enricher.py:66-118`) overwrites `regime` via `regime_from_strength` → `{TREND_UP, TREND_DOWN, NEUTRAL}` (`trend_features_batch.py:297-302`). `ENRICH_VERSION = "trend_features_v1"`.

`certified_tick_cache_present` (`tick_cache_persist.py:164-191`) requires:

- ticks + split files non-empty
- `train_hash` present
- `actual_calendar_days >= 86`
- `requested_days >= 90`
- `tick_count >= 1_000`

**Cloud implication:** the user default of “≥ 10 trading days” is **below** the Foundation start rung. Meet the 90-day floor; do not patch it away (`foundation_history.py:22-27`, `FOUNDATION_HISTORY_START_DAYS = 90`).

## 3. Cache reuse vs Fabric / practice_mode

Launcher skip (`birth_runner_start.py:50-72`):

- `practice_mode` → skip Fabric probe (also sets `training_mode="practice"` — **rejected** for this run).
- `force=True` → **does not skip** launcher Fabric preflight.
- `reuse_data + certified_cache` (no continue) → skip Fabric.

Engine reuse (`data_pipeline_resume.py:80-88`): `_reuse_data_manifest=True` loads jsonl even when `force=True` (resume=False, plant is clean). Log path: `reused_manifest=True` in `certificate_preflight.py:78`.

**Choice:** certified-shaped cache + `practice_mode=False` + call `BirthPhaseEngineV2.run_birth_phase(..., reuse_data_manifest=True)` **directly** (bypass launcher thread). Stage floors / `is_birth_exit_sufficient` unchanged.

## 4. Headless construct (same objects the app uses)

From `birth_runner_start.py:394-439` (no `container.start()` — that is the broker connect):

1. `LUMINA_CONFIG=<workspace>/config.yaml`
2. `ApplicationContainer()`
3. `_bind_headless_runtime_app(container)` (`runtime_mode_runners.py:97-126`)
4. `BirthPhaseEngineV2(runtime=container.engine, ppo_trainer=container.ppo_trainer, market_data_service=..., workspace_root=...)`

Do **not** call `container.start()` (would `broker.connect()`, `container_lifecycle.py:164-185`).

`supported_swarm_roots` default is `MES, MNQ, MYM, ES` (`engine_config.py:80`). Workspace overlay sets `trading.instrument: NQ SEP26`; validation uses `config.swarm_symbols` (checked **before** primary is inserted), so NQ as primary is allowed.

## 5. Birth exit contract (call, do not reinvent)

`is_birth_exit_sufficient` (`maturity/birth_exit.py:344-345`) ≡ `evaluate_birth_exit(...).exited`.

ALL of:

- five `foundation_v2` receipts for `ordered_stages()` S1–S5, each `verify_stage_pass_receipt(..., training_mode="certified")`
- checksum-consistent `state/lumina_birth_fitness_vector.json` vs S5 receipt

Filename SSOT: `FITNESS_VECTOR_NAME = "lumina_birth_fitness_vector.json"` (`fitness_vector.py:17`).

Explicitly **not** required: Perfect Birth, Evolution Proof, deck, first SIM order, PromotionGate, OOS WR 0.48, NT connectivity (ADR-0036 §2).

Stage floors (ADR-0046 / `birth-curriculum-stage-floors.md`): process-R + occupancy + first-touch. **Never WR 20/35/40 as pass law.**

## 6. Existing synthetic generators — do not reuse as the cache

`generate_synthetic_ticks` (`data_pipeline_types.py:44-65`) is a **practice toy**: identical `datetime.now()` timestamps, regime=`SYNTHETIC`, source=`synthetic`, no session calendar. Engine ignores it when `prefer_real_data_only` and cache miss. Cloud fixture **must** write the real jsonl+split+manifest schema.

## 7. Holdout preflight

`assess_split_preflight` (`preflight.py:40-76`): ≥ `min_regimes` (3), holdout ticks ≥ 500, estimated trades ≥ 50. Holdout is last 20% of **calendar days** (`purged_split.py`, `holdout_pct=0.20`). Fixture must put all three enricher regimes in the last ~18 days.

## 8. Checkpoint / autonomy

- Checkpoint: `state/lumina_birth_checkpoint.json` (`checkpoint.py:18-23`), includes `stage_metrics.stage_trades`, `stages_passed`, `data_manifest`.
- Resume: `can_resume_checkpoint` + `force=False` restores stage (`birth_phase_bootstrap.py:137-160`).
- Default `checkpoint_interval_sec=600` (`config_curriculum.py:76`). Cloud workspace overlay may lower **interval only** (not floors) so crash/resume is observable inside the wall.

## 9. Capital

Root `config.yaml:1` is `mode: sim`. This run copies that into an isolated workspace and **never** calls `container.start()` / live broker. `prefer_real_data_only=true` against the fixture cache. Source label on ticks: `synthetic_cloud_fixture` (honest; `real_data_percentage` will be 0 — that fails **certificate** min_real_data_pct 95%, which is Proving Ground, not Birth exit).
