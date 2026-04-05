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