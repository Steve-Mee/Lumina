#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/.env.production"
ENV_EXAMPLE="$ROOT_DIR/deploy/.env.production.example"

log() {
  echo "[lumina-smoke] $1"
}

fail() {
  echo "[lumina-smoke] FAIL: $1" >&2
  exit 1
}

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

wait_for_vllm_health() {
  local retries=40
  local delay=5
  for ((i=1; i<=retries; i++)); do
    if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

log "starting pre-prod smoke checks"
command -v docker >/dev/null 2>&1 || fail "docker not found"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin not found"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  log "created deploy/.env.production from example"
fi

cd "$ROOT_DIR"

if detect_vllm_compatible_gpu; then
  log "compatible GPU detected; running full stack smoke (vLLM + lumina)"
  docker compose -f docker-compose.prod.yml --profile vllm up -d --build

  if wait_for_vllm_health; then
    log "vLLM health endpoint is ready"
    curl -fsS "http://127.0.0.1:8000/v1/models" >/dev/null
    log "vLLM model endpoint responded"
  else
    docker compose -f docker-compose.prod.yml logs vllm --tail=200 || true
    fail "vLLM did not become healthy"
  fi
else
  log "no compatible GPU sm_70+ detected; running fallback-only smoke"
  docker compose -f docker-compose.prod.yml up -d --build
  docker compose -f docker-compose.prod.yml stop vllm >/dev/null 2>&1 || true
fi

sleep 5
if ! docker compose -f docker-compose.prod.yml ps lumina | grep -q "Up"; then
  docker compose -f docker-compose.prod.yml logs lumina --tail=200 || true
  fail "lumina service is not running"
fi

log "lumina service is running"
log "smoke checks completed successfully"