# Release Workflow

This repository is configured so the future production machine can update from release tags instead of tracking every commit.

## Recommended release model

- Use semantic-ish tags with a `v` prefix, for example:
  - `v1.0.0`
  - `v1.0.1`
  - `v1.1.0`
- Keep production auto-update mode on `tag`.

## Why tags

- Production machines should not automatically deploy every commit.
- A tag gives you an explicit checkpoint that has already been tested.
- The deployed machine can safely move only to the newest approved release.

## Suggested release steps

1. Finish changes in the test environment.
2. Run the relevant regression suite.
3. Commit the tested changes.
4. Create a release tag.
5. Push the branch and the tag.
6. Let the production updater move to the newest matching tag.

## Example commands

```bash
git checkout main
git pull --ff-only
git tag v1.0.0
git push origin main
git push origin v1.0.0
```

## One-command helper

You can use the repository helper to run the regression gate and publish a release tag:

```bash
bash deploy/release.sh v1.0.0
```

What it does:

- Verifies a clean git working tree
- Syncs `main` with origin
- Runs the core regression suite (`test_local_inference_engine`, `test_lumina_engine_suite`, `test_runtime_workers`)
- Creates the tag
- Pushes `main` and the tag

## How the production updater behaves

- `deploy/update_stack.sh` reads `deploy/.env.production`.
- If `LUMINA_UPDATE_MODE=tag`, it finds the newest tag matching `LUMINA_RELEASE_PREFIX`.
- It checks out that tag in detached mode and rebuilds/restarts the Docker stack.

## Pinning to a specific release

If you want to hold production on one exact release:

```bash
LUMINA_UPDATE_MODE=tag
LUMINA_RELEASE_PREFIX=v
LUMINA_RELEASE_REF=v1.0.0
```

With that setting, the updater stays on the pinned tag until you change the value.

## Branch mode

Branch mode still exists, but it is less safe for production:

```bash
LUMINA_UPDATE_MODE=branch
LUMINA_UPDATE_BRANCH=main
```

Use this only if you intentionally want the machine to follow a moving branch.

## Release Note Template (SIM Overnight Hardening)

Use this format for release notes when publishing operational SIM/REAL behavior changes.

### Title

`Hardened Overnight SIM Learning Mode (SIM-first)`

### Summary

This release strengthens overnight SIM edge-discovery while preserving strict REAL risk discipline.

### Scope

- Added CLI support for overnight simulation mode: `--overnight-sim`.
- Added headless runtime handling for `sim_overnight_mode` with 240-minute equivalent execution behavior and explicit summary output.
- Expanded aggressive SIM learning boost context to 24h + 7d + 30d with a floor target of 200k.
- Added explicit aggressive start/end log markers for operator visibility.
- Added config default: `headless.sim_overnight_mode: false`.

### Impact

- SIM mode can run more aggressive exploratory adaptation during overnight validation windows.
- REAL safety posture remains unchanged (capital preservation and strict controls).
- Operators can confirm overnight behavior directly from run summary payloads.

### Validation Evidence

Run command:

```bash
python -m lumina_launcher --mode=sim --headless --duration=240 --overnight-sim
```

Acceptance outcomes:

- Realized PnL: positive
- Sharpe annualized: > 2.0
- Evolution proposals: > 50
- Risk events: 0

Example observed values (2026-04-09):

- `pnl_realized`: 18384.8
- `sharpe_annualized`: 2.5419
- `evolution_proposals`: 74
- `sim_overnight_mode`: true
- `risk_events`: 0

### Safety Gate Status

- `pytest -m safety_gate -q` passed after this change set.

### Rollback

- Disable overnight behavior by omitting `--overnight-sim`.
- Keep `headless.sim_overnight_mode: false` in environment config.
- If needed, roll back to the previous release tag and redeploy via the standard tag workflow.

### Operator Notes

- Prefer this mode for controlled SIM learning windows only.
- Use SIM validation evidence as a mandatory input before any REAL progression decision.