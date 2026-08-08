"""Monitoring JSONL writers (M5 extract from logging_utils)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from lumina_core.logging_core import _MONITORING_IO_LOCK

def resolve_monitoring_state_dir() -> Path:
    """Workspace ``state/`` directory (never rely on process cwd alone)."""
    override = os.getenv("LUMINA_WORKSPACE_ROOT", "").strip()
    if override:
        return (Path(override).expanduser().resolve() / "state")
    config_path = os.getenv("LUMINA_CONFIG", "").strip()
    if config_path:
        return Path(config_path).expanduser().resolve().parent / "state"
    cwd = Path.cwd()
    for candidate in (cwd, Path(__file__).resolve().parents[1]):
        if (candidate / "state").is_dir() and (candidate / "lumina_core").exists():
            return (candidate / "state").resolve()
    return (cwd / "state").resolve()


def _monitoring_state_path(name: str) -> Path:
    return resolve_monitoring_state_dir() / name


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=True, sort_keys=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MONITORING_IO_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _MONITORING_IO_LOCK:
        path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def record_twin_decision_monitoring(
    *,
    dna_hash: str,
    score: float,
    recommendation: bool,
    risk_flags: list[str],
    explanation: str,
    source: str = "approval_twin",
    mode: str = "",
    outcome: str | None = None,
) -> None:
    flags = list(risk_flags or [])
    classified = outcome if outcome is not None else classify_twin_decision_outcome(
        recommendation=bool(recommendation),
        score=float(score),
        risk_flags=flags,
    )
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(source),
        "dna_hash": str(dna_hash),
        "score": float(score),
        "recommendation": bool(recommendation),
        "risk_flags": flags,
        "explanation": str(explanation),
        "outcome": str(classified),
    }
    if mode:
        payload["mode"] = str(mode)
    _append_jsonl(_monitoring_state_path("monitoring_twin_decisions.jsonl"), payload)


def record_twin_training_metrics_monitoring(*, avg_prediction_error: float, reward: float, training_steps: int) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "avg_prediction_error": float(avg_prediction_error),
        "reward": float(reward),
        "training_steps": int(training_steps),
    }
    _append_jsonl(_monitoring_state_path("monitoring_twin_training.jsonl"), payload)


def record_gate_rejection_monitoring(
    *,
    gate_name: str,
    reason: str,
    mode: str = "",
    symbol: str = "",
    side: str = "",
    decision_context_id: str = "",
) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate_name": str(gate_name),
        "reason": str(reason),
        "mode": str(mode),
        "symbol": str(symbol),
        "side": str(side),
        "decision_context_id": str(decision_context_id),
    }
    _append_jsonl(_monitoring_state_path("monitoring_gate_rejections.jsonl"), payload)


def record_model_load_time_monitoring(
    *,
    model_type: str,
    model_path: str,
    load_time_sec: float,
    status: str,
) -> None:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model_type": str(model_type),
        "model_path": str(model_path),
        "load_time_sec": float(load_time_sec),
        "status": str(status),
    }
    _append_jsonl(_monitoring_state_path("monitoring_model_load_times.jsonl"), payload)


def write_ppo_policy_metadata(
    *,
    policy_path: str,
    policy_version: str,
    total_training_steps: int,
    training_time_sec: float = 0.0,
    last_load_time_sec: float = 0.0,
    status: str = "ok",
    observation_dim: int | None = None,
) -> None:
    if observation_dim is None:
        from lumina_core.rl.observation_builder import OBSERVATION_DIM

        observation_dim = OBSERVATION_DIM
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy_path": str(policy_path),
        "policy_version": str(policy_version),
        "total_training_steps": int(total_training_steps),
        "training_time_sec": float(training_time_sec),
        "last_load_time_sec": float(last_load_time_sec),
        "status": str(status),
        "observation_dim": int(observation_dim),
    }
    _write_json(_monitoring_state_path("ppo_policy_metadata.json"), payload)


def write_runtime_monitoring_snapshot(payload: dict[str, Any]) -> None:
    base = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    base.update(payload if isinstance(payload, dict) else {})
    _write_json(_monitoring_state_path("monitoring_runtime_metrics.json"), base)
    if "daily_pnl" in base:
        try:
            _append_jsonl(
                _monitoring_state_path("monitoring_daily_pnl.jsonl"),
                {"timestamp": str(base["timestamp"]), "daily_pnl": float(base["daily_pnl"])},
            )
        except (TypeError, ValueError):
            pass


def record_reasoning_latency_monitoring(
    *,
    source: str,
    elapsed_ms: float,
    sla_ms: float,
    breach_streak: int,
    fast_path_only: bool,
    daily_pnl: float | None = None,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(source),
        "elapsed_ms": float(elapsed_ms),
        "sla_ms": float(sla_ms),
        "breach_streak": int(breach_streak),
        "fast_path_only": bool(fast_path_only),
    }
    if daily_pnl is not None:
        payload["daily_pnl"] = float(daily_pnl)
    _append_jsonl(_monitoring_state_path("monitoring_reasoning_latency.jsonl"), payload)


# =============================================================================
# Autonomy snapshot + Perfect Birth Phase metrics (added for measurable success KPIs)
# Implements referenced-but-missing compute_autonomy_snapshot + recorders.
# Used by RuntimeTwinOversight and birth autonomy observability.
# =============================================================================

def classify_twin_decision_outcome(*, recommendation: bool, score: float, risk_flags: list[str] | None = None) -> str:
    """Classify twin outcome for autonomy calculations (matches runtime_twin_oversight._classify_outcome)."""
    conf = float(score or 0.0)
    risks = list(risk_flags or [])
    _AUTO_CONF = 0.80
    if conf >= _AUTO_CONF:
        if recommendation and not risks:
            return "auto_approved"
        if not recommendation:
            return "veto"
    return "deferred"


def record_autonomy_metrics_monitoring(autonomy: dict[str, Any]) -> None:
    """Append hourly/rollup autonomy metrics (used by RuntimeTwinOversight.maybe_record_autonomy_rollup)."""
    payload: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if isinstance(autonomy, dict):
        payload.update(autonomy)
    _append_jsonl(_monitoring_state_path("monitoring_autonomy_metrics.jsonl"), payload)


def record_twin_steve_accuracy_monitoring(*, agreement_pct: float, samples: int, avg_error: float | None = None) -> None:
    """Record twin vs Steve label agreement % (core 'twin accuracy vs Steve' KPI for Perfect Birth Phase)."""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "twin_steve_agreement_pct": round(float(agreement_pct or 0.0), 2),
        "samples": int(samples or 0),
    }
    if avg_error is not None:
        payload["avg_prediction_error"] = float(avg_error)
    _append_jsonl(_monitoring_state_path("monitoring_twin_training.jsonl"), payload)


def record_shadow_twin_alignment_monitoring(
    *,
    aligned: bool,
    shadow_pnl: float,
    twin_recommendation: bool,
    confidence: float | None = None,
    dna_hash: str = "",
) -> None:
    """Record alignment between twin decision and shadow outcome (for shadow/twin alignment KPI)."""
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "aligned": bool(aligned),
        "shadow_pnl": float(shadow_pnl or 0.0),
        "twin_recommendation": bool(twin_recommendation),
        "dna_hash": str(dna_hash or "")[:64],
    }
    if confidence is not None:
        payload["confidence"] = float(confidence)
    _append_jsonl(_monitoring_state_path("monitoring_shadow_twin_alignment.jsonl"), payload)
