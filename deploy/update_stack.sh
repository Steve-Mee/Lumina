#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env.production"

detect_vllm_compatible_gpu() {
	if ! command -v nvidia-smi >/dev/null 2>&1; then
		return 1
	fi

	local cc
	cc="$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -n 1 | tr -d '[:space:]')"
	if [[ -z "$cc" ]]; then
		return 1
	fi

	local major
	major="${cc%%.*}"
	[[ "$major" =~ ^[0-9]+$ ]] || return 1
	(( major >= 7 ))
}

if [[ -f "$ENV_FILE" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +a
fi

cd "$ROOT_DIR"

echo "[lumina] fetching latest repository state"
git fetch --all --tags --prune

UPDATE_MODE="${LUMINA_UPDATE_MODE:-tag}"
RELEASE_PREFIX="${LUMINA_RELEASE_PREFIX:-v}"
RELEASE_REF="${LUMINA_RELEASE_REF:-}"
UPDATE_BRANCH="${LUMINA_UPDATE_BRANCH:-main}"

if [[ "$UPDATE_MODE" == "tag" ]]; then
	if [[ -n "$RELEASE_REF" ]]; then
		TARGET_REF="$RELEASE_REF"
	else
		TARGET_REF="$(git tag --list "${RELEASE_PREFIX}*" --sort=-version:refname | head -n 1)"
	fi

	if [[ -z "$TARGET_REF" ]]; then
		echo "[lumina] no release tag found for prefix '${RELEASE_PREFIX}'"
		exit 1
	fi

	CURRENT_TAG="$(git describe --tags --exact-match 2>/dev/null || true)"
	if [[ "$CURRENT_TAG" != "$TARGET_REF" ]]; then
		echo "[lumina] checking out release tag $TARGET_REF"
		git checkout --detach "tags/$TARGET_REF"
	else
		echo "[lumina] already on release tag $TARGET_REF"
	fi
else
	echo "[lumina] updating branch $UPDATE_BRANCH"
	git checkout "$UPDATE_BRANCH"
	git pull --ff-only origin "$UPDATE_BRANCH"
fi

echo "[lumina] refreshing images and rebuilding local services"
if detect_vllm_compatible_gpu; then
	echo "[lumina] compatible GPU detected; updating with vLLM profile"
	docker compose -f docker-compose.prod.yml pull vllm || true
	docker compose -f docker-compose.prod.yml --profile vllm up -d --build
else
	echo "[lumina] vLLM profile skipped (no compatible GPU sm_70+); fallback providers remain active"
	docker compose -f docker-compose.prod.yml up -d --build
	docker compose -f docker-compose.prod.yml stop vllm >/dev/null 2>&1 || true
fi

echo "[lumina] pruning dangling images"
docker image prune -f >/dev/null 2>&1 || true

echo "[lumina] service status"
docker compose -f docker-compose.prod.yml ps
