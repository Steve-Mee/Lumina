"""Birth endpoint status enrichment helpers (global residual)."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any

from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.services.birth_status_diagnostics import merge_certificate_diagnostics
from lumina_core.birth.birth_certificate import validate_certificate_artifacts
from lumina_core.birth.checkpoint import load_checkpoint_state
from lumina_core.birth.config import BRO_ENGINE_VERSION, load_birth_v2_config
from lumina_core.birth.remediation import should_fast_path_remediation_from_state

_ENRICH_ARTIFACT_CACHE_TTL_SEC = 20.0
_ENRICH_ARTIFACT_CACHE: tuple[float, dict[str, Any]] | None = None
_ENRICH_ARTIFACT_LOCK = Lock()
_ACTIVE_BIRTH_POLL_PHASES = frozenset(
    {
        "loading_history",
        "loading_history_failed",
        "enriching_news",
        "enriching_regimes",
        "train_holdout_split",
        "holdout_preflight",
        "holdout_preflight_expansion",
        "policy_init",
        "ticks_ready",
        "curriculum_stage",
        "curriculum_learning",
        "curriculum_research",
        "ppo_training",
        "parallel_simulation",
    }
)
_ENRICH_ARTIFACT_KEYS = (
    "birth_exit_ok",
    "artifacts_ok",
    "certificate_ok",
    "certificate_reason",
    "evolution_proof_ok",
    "real_trading_eligible",
    "certificate",
    "artifacts_label",
    "fast_path_eligible",
    "checkpoint_phase",
    "checkpoint_quality_score",
    "checkpoint_resumable",
    "checkpoint_ppo_steps",
    "checkpoint_cumulative_trades",
    "checkpoint_stage_trades",
)

def _is_active_birth_poll(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status", "") or "").strip().lower()
    if status == "running":
        return True
    progress = payload.get("progress")
    if not isinstance(progress, dict):
        return False
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if stage == "loading_data":
        return True
    return phase in _ACTIVE_BIRTH_POLL_PHASES

def _apply_progress_fields(payload: dict[str, Any], *, checkpoint: dict[str, Any] | None = None) -> str:
    progress = payload.get("progress")
    progress_phase = ""
    if isinstance(progress, dict):
        progress_phase = str(progress.get("phase", "") or "").strip().lower()
        diag = merge_certificate_diagnostics(progress, checkpoint)
        payload["curriculum_stage"] = progress.get("curriculum_stage")
        payload["oos_metrics"] = diag.get("oos_metrics") or progress.get("oos_metrics")
        payload["failure_reasons"] = diag.get("failure_reasons") or (
            (progress.get("oos_metrics") or {}).get("failure_reasons")
            if isinstance(progress.get("oos_metrics"), dict)
            else None
        )
        payload["runway_phase"] = diag.get("runway_phase") or progress.get("runway_phase")
        payload["birth_exit_winrate"] = diag.get("birth_exit_winrate")
        if isinstance(progress, dict) and diag.get("oos_metrics"):
            merged_progress = dict(progress)
            merged_progress["oos_metrics"] = diag["oos_metrics"]
            if diag.get("failure_reasons"):
                merged_progress.setdefault("failure_reasons", diag["failure_reasons"])
            payload["progress"] = merged_progress
        payload["quality_score"] = progress.get("quality_score")
        payload["remediation_attempt"] = progress.get("remediation_attempt")
        payload["remediation_max"] = progress.get("remediation_max")
        payload["data_manifest"] = progress.get("data_manifest")
        # Phase D readiness (honest absence; never hollow declare).
        for key in (
            "certificate_present",
            "evolution_proof_present",
            "perfect_birth_flag_present",
            "certificate_path_ready",
            "certificate_readiness_blockers",
            "perfect_birth_would_pass",
            "perfect_birth_unlock_valid",
            "perfect_birth_failures",
            "curriculum_stages_passed_count",
            "expectancy_quality_step",
            "expectancy_stall_detected",
            "evolution_actions_completed",
            "plateau_evolution_max_steps_effective",
        ):
            if key in progress:
                payload[key] = progress.get(key)
    return progress_phase

def _enrich_status_full(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach SSOT artifact readiness (Birth Certificate v2 + policy zip)."""
    root = birth_service.workspace_root
    thresholds = load_birth_v2_config(root).certificate_thresholds
    cert_ok, cert_reason, cert = validate_certificate_artifacts(root, thresholds=thresholds)
    ckpt = load_checkpoint_state(root)
    progress_phase = _apply_progress_fields(payload, checkpoint=ckpt if isinstance(ckpt, dict) else None)
    resumable = birth_service.checkpoint_resumable()
    payload["checkpoint_resumable"] = resumable
    if resumable and ckpt:
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")
        payload.setdefault("checkpoint_phase", ckpt.get("phase"))
        payload.setdefault("checkpoint_quality_score", ckpt.get("quality_score"))
        payload["checkpoint_ppo_steps"] = int(ckpt.get("ppo_steps", 0) or 0)
        payload["checkpoint_cumulative_trades"] = int(ckpt.get("cumulative_trades", 0) or 0)
        payload["curriculum_stage"] = ckpt.get("curriculum_stage") or payload.get("curriculum_stage")
        stage_metrics = ckpt.get("stage_metrics")
        if isinstance(stage_metrics, dict):
            payload["checkpoint_stage_trades"] = int(stage_metrics.get("stage_trades", 0) or 0)
    elif isinstance(ckpt, dict) and ckpt:
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")
        payload.setdefault("checkpoint_phase", ckpt.get("phase"))
        payload.setdefault("checkpoint_quality_score", ckpt.get("quality_score"))
    if progress_phase in {"certificate_failed", "certificate_remediation"}:
        failure_reasons = payload.get("failure_reasons")
        if isinstance(failure_reasons, list) and failure_reasons:
            cert_reason = "; ".join(str(item) for item in failure_reasons)
    payload["artifacts_ok"] = birth_service.artifacts_ok()
    try:
        from lumina_core.maturity.birth_exit import is_birth_exit_sufficient

        payload["birth_exit_ok"] = bool(is_birth_exit_sufficient(root))
    except Exception:
        payload["birth_exit_ok"] = False
    payload["certificate_ok"] = cert_ok
    payload["certificate_reason"] = cert_reason
    payload["evolution_proof_ok"] = birth_service.evolution_proof_ok()
    payload["real_trading_eligible"] = birth_service.real_trading_eligible()
    payload["certificate"] = cert.model_dump(mode="json") if cert is not None else None
    payload["artifacts_label"] = (
        "Birth Certificate v2 OK" if payload["artifacts_ok"] else "Certificate or policy missing"
    )
    payload["phase_label"] = "Birth Phase v2"
    payload["engine_version"] = BRO_ENGINE_VERSION
    progress_for_fast_path = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    payload["fast_path_eligible"] = should_fast_path_remediation_from_state(
        progress_for_fast_path,
        ckpt if isinstance(ckpt, dict) else {},
    )
    from lumina_launcher.services.birth_maturity_wiring import maturity_status_fields

    payload.update(maturity_status_fields(root))
    return payload

def _apply_fresh_checkpoint_resumable(payload: dict[str, Any]) -> None:
    """Always recompute resume SSOT from disk (cheap) so cold restart is accurate."""
    ckpt = load_checkpoint_state(birth_service.workspace_root)
    resumable = birth_service.checkpoint_resumable()
    payload["checkpoint_resumable"] = resumable
    if isinstance(ckpt, dict) and ckpt:
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")
        payload.setdefault("checkpoint_phase", ckpt.get("phase"))
        payload.setdefault("checkpoint_quality_score", ckpt.get("quality_score"))
        if resumable:
            payload["checkpoint_ppo_steps"] = int(ckpt.get("ppo_steps", 0) or 0)
            payload["checkpoint_cumulative_trades"] = int(ckpt.get("cumulative_trades", 0) or 0)
            payload["curriculum_stage"] = ckpt.get("curriculum_stage") or payload.get(
                "curriculum_stage"
            )
            stage_metrics = ckpt.get("stage_metrics")
            if isinstance(stage_metrics, dict):
                payload["checkpoint_stage_trades"] = int(
                    stage_metrics.get("stage_trades", 0) or 0
                )


def _enrich_status(payload: dict[str, Any]) -> dict[str, Any]:
    """Enrich status; cache expensive cert fields, always refresh checkpoint_resumable.

    Cold restart used to run full certificate validation on every idle/interrupted
    poll, delaying Genesis recovery controls. Cache the heavy fields; resume SSOT
    stays live from disk.
    """
    global _ENRICH_ARTIFACT_CACHE
    now = time.time()
    ckpt = load_checkpoint_state(birth_service.workspace_root)
    progress_phase = _apply_progress_fields(
        payload,
        checkpoint=ckpt if isinstance(ckpt, dict) else None,
    )
    if isinstance(ckpt, dict):
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")

    with _ENRICH_ARTIFACT_LOCK:
        cached = _ENRICH_ARTIFACT_CACHE
    if cached is not None:
        cached_at, artifact_fields = cached
        if (now - cached_at) < _ENRICH_ARTIFACT_CACHE_TTL_SEC:
            payload.update(artifact_fields)
            payload["phase_label"] = "Birth Phase v2"
            payload["engine_version"] = BRO_ENGINE_VERSION
            # Resume SSOT must not be stale from cache (wipe / stop race).
            _apply_fresh_checkpoint_resumable(payload)
            if progress_phase in {"certificate_failed", "certificate_remediation"}:
                failure_reasons = payload.get("failure_reasons")
                if isinstance(failure_reasons, list) and failure_reasons:
                    payload["certificate_reason"] = "; ".join(
                        str(item) for item in failure_reasons
                    )
            return payload

    enriched = _enrich_status_full(payload)
    artifact_fields = {key: enriched[key] for key in _ENRICH_ARTIFACT_KEYS if key in enriched}
    with _ENRICH_ARTIFACT_LOCK:
        _ENRICH_ARTIFACT_CACHE = (now, artifact_fields)
    return enriched

def _build_birth_status_payload() -> dict[str, Any]:
    return _enrich_status(birth_service.get_status())

def _invalidate_enrich_artifact_cache() -> None:
    global _ENRICH_ARTIFACT_CACHE
    with _ENRICH_ARTIFACT_LOCK:
        _ENRICH_ARTIFACT_CACHE = None

def _merge_start_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep start acknowledgement when enriching with polled status."""
    payload: dict[str, Any] = dict(result)
    start_status = str(result.get("status", "") or "").strip().lower()
    if start_status not in {"started", "already_running"}:
        return payload
    live = birth_service.get_status()
    payload.update(live)
    payload["status"] = start_status
    payload["start_acknowledged"] = True
    if result.get("message"):
        payload.setdefault("start_message", result.get("message"))
    return payload
