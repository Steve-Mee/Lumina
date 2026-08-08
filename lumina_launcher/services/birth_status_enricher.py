"""Birth status enrichment: diagnostics, launcher setup, plateau risk (extracted from birth_service)."""

from __future__ import annotations

import time
from typing import Any, Dict

from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager
from lumina_core.logging_utils import get_logger
from lumina_launcher.core.setup_gate import launcher_setup_status_payload
from lumina_launcher.services.birth_status_diagnostics import merge_certificate_diagnostics
from lumina_launcher.services.birth_status_mapper import should_use_lightweight_status_enrichment
from lumina_launcher.services.birth_status_plateau_risk import resume_plateau_risk_fields

logger = get_logger(__name__)
_LAUNCHER_SETUP_CACHE_TTL_SEC = 60.0


def get_adaptive_intelligence_manager(svc: Any) -> AdaptiveIntelligenceManager:
    if svc._adaptive_intelligence_manager is None:
        svc._adaptive_intelligence_manager = AdaptiveIntelligenceManager(svc.workspace_root)
    return svc._adaptive_intelligence_manager


def launcher_setup_status(svc: Any, *, lightweight: bool = False) -> dict[str, Any]:
    now = time.time()
    # Active birth polls stay snappy: never hit launcher setup payload while running.
    if lightweight and bool(svc.is_running()):
        return {}
    if (
        svc._launcher_setup_cache is not None
        and (now - svc._launcher_setup_cached_at) < _LAUNCHER_SETUP_CACHE_TTL_SEC
    ):
        return svc._launcher_setup_cache
    try:
        payload = launcher_setup_status_payload(svc.workspace_root)
    except Exception as exc:
        logger.warning("birth.launcher_setup.status_failed detail=%s", exc)
        payload = {
            "setup_complete": False,
            "intelligence_stack_ready": False,
            "needs_smart_setup": True,
            "needs_guided_setup": False,
            "launcher_ready": False,
            "recommended_model": "",
            "recommended_provider": "ollama",
            "recommended_ollama_tag": "",
            "missing": ["launcher_setup_status_failed"],
        }
    svc._launcher_setup_cache = payload
    svc._launcher_setup_cached_at = now
    return payload


def adaptive_intelligence_status(svc: Any, *, lightweight: bool = False) -> Dict[str, Any]:
    try:
        # Cold session probe: do not construct HardwareIntelligenceManager on the
        # first status poll — that can stall Genesis for seconds after app restart.
        if lightweight and getattr(svc, "_adaptive_intelligence_manager", None) is None:
            return {
                "tier": "light",
                "mode": "auto",
                "reasoning_mode": "fast_path_only",
                "degraded_state": False,
                "status_reason": "deferred_cold_start",
                "recommended_model": "",
                "recommended_provider": "ollama",
                "context_length": 0,
                "last_probe_error": None,
            }
        manager = get_adaptive_intelligence_manager(svc)
        if lightweight:
            cached = manager.get_status()
            return cached.to_dict()
        return manager.to_dict()
    except Exception as exc:
        logger.warning("birth.adaptive_intelligence.status_failed detail=%s", exc)
        return {
            "tier": "light",
            "mode": "auto",
            "reasoning_mode": "fast_path_only",
            "degraded_state": True,
            "status_reason": "adaptive_intelligence_init_failed",
            "recommended_model": "",
            "recommended_provider": "ollama",
            "context_length": 0,
            "last_probe_error": str(exc),
        }


def enrich_birth_status(svc: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    progress = payload.get("progress")
    progress_dict = progress if isinstance(progress, dict) else {}
    lightweight = should_use_lightweight_status_enrichment(svc, progress_dict)
    if isinstance(progress, dict):
        from lumina_core.birth.checkpoint import load_checkpoint_state

        ckpt = load_checkpoint_state(svc.workspace_root)
        diag = merge_certificate_diagnostics(progress, ckpt if isinstance(ckpt, dict) else None)
        if diag.get("oos_metrics"):
            payload["oos_metrics"] = diag["oos_metrics"]
        if diag.get("failure_reasons"):
            payload["failure_reasons"] = diag["failure_reasons"]
        if diag.get("runway_phase"):
            payload["runway_phase"] = diag["runway_phase"]
        if diag.get("birth_exit_winrate") is not None:
            payload["birth_exit_winrate"] = diag["birth_exit_winrate"]
    payload["launcher_setup"] = launcher_setup_status(svc, lightweight=lightweight)
    payload.update(resume_plateau_risk_fields(svc))
    if not lightweight:
        from lumina_launcher.services.birth_maturity_wiring import maturity_status_fields

        payload.update(maturity_status_fields(svc.workspace_root))
    return payload


__all__ = [
    "adaptive_intelligence_status",
    "enrich_birth_status",
    "get_adaptive_intelligence_manager",
    "launcher_setup_status",
    "resume_plateau_risk_fields",
    "should_use_lightweight_status_enrichment",
]