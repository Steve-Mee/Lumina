#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: bash deploy/release.sh vX.Y.Z"
  exit 1
fi

if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid version '$VERSION'. Expected format: vX.Y.Z"
  exit 1
fi

cd "$ROOT_DIR"

echo "[release] checking git working tree"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty. Commit or stash changes first."
  exit 1
fi

echo "[release] syncing main"
git checkout main
git pull --ff-only origin main

echo "[release] running regression gate"
./.venv/Scripts/python.exe -m pytest tests/test_local_inference_engine.py tests/engine/test_lumina_engine_suite.py -q
./.venv/Scripts/python.exe -m pytest tests/test_runtime_workers.py -q

if git rev-parse "$VERSION" >/dev/null 2>&1; then
  echo "Tag '$VERSION' already exists locally."
  exit 1
fi

echo "[release] creating tag $VERSION"
git tag "$VERSION"

echo "[release] pushing branch + tag"
git push origin main
git push origin "$VERSION"

echo "[release] done: $VERSION"
