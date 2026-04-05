#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "[lumina-preflight] FAIL: $1" >&2
  exit 1
}

pass() {
  echo "[lumina-preflight] OK: $1"
}

warn() {
  echo "[lumina-preflight] WARN: $1"
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

echo "[lumina-preflight] checking production machine prerequisites"

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
pass "docker is installed"

docker compose version >/dev/null 2>&1 || fail "docker compose plugin is not available"
pass "docker compose plugin is available"

if command -v nvidia-smi >/dev/null 2>&1; then
  pass "nvidia-smi is available"
  if detect_vllm_compatible_gpu; then
    pass "GPU compute capability is compatible with vLLM (sm_70+)"
  else
    warn "GPU compute capability appears below sm_70; vLLM profile will be skipped and fallback providers will be used"
  fi
else
  warn "nvidia-smi not found; vLLM profile will be skipped and fallback providers will be used"
fi

if ! docker info >/dev/null 2>&1; then
  fail "docker daemon is not reachable"
fi
pass "docker daemon is reachable"

if docker info --format '{{json .Runtimes}}' | grep -qi nvidia; then
  pass "NVIDIA container runtime detected"
else
  warn "NVIDIA container runtime not detected; vLLM profile will be skipped and fallback providers will be used"
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="$ROOT_DIR/deploy/.env.production.example"
ENV_FILE="$ROOT_DIR/deploy/.env.production"

[[ -f "$ENV_EXAMPLE" ]] || fail "missing deploy/.env.production.example"
pass "deploy/.env.production.example exists"

if [[ ! -f "$ENV_FILE" ]]; then
  warn "deploy/.env.production does not exist yet; copy it from the example before install"
else
  pass "deploy/.env.production exists"
fi

if [[ ! -f "$ROOT_DIR/docker-compose.prod.yml" ]]; then
  fail "missing docker-compose.prod.yml"
fi
pass "docker-compose.prod.yml exists"

if [[ ! -f "$ROOT_DIR/deploy/config.production.yaml" ]]; then
  fail "missing deploy/config.production.yaml"
fi
pass "deploy/config.production.yaml exists"

echo "[lumina-preflight] all critical checks passed"