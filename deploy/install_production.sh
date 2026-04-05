#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env.production"
ENV_EXAMPLE="$ROOT_DIR/deploy/.env.production.example"

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

echo "[lumina] checking docker prerequisites"
command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "docker compose plugin not found"; exit 1; }

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "[lumina] created $ENV_FILE from example; fill in secrets before production use"
fi

echo "[lumina] starting production stack"
cd "$ROOT_DIR"

if detect_vllm_compatible_gpu; then
  echo "[lumina] compatible GPU detected; starting with vLLM profile"
  docker compose -f docker-compose.prod.yml --profile vllm up -d --build
else
  echo "[lumina] vLLM profile skipped (no compatible GPU sm_70+); fallback providers will be used"
  docker compose -f docker-compose.prod.yml up -d --build
fi

echo "[lumina] current service status"
docker compose -f docker-compose.prod.yml ps
