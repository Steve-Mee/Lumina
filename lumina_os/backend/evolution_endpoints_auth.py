"""Evolution endpoint auth/io helpers (M5)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Header, HTTPException
from lumina_core.audit import get_audit_logger

logger = logging.getLogger(__name__)

_obs_service: Any = None
_SECURITY_MODULE: dict[str, Any] | None = None

_EVOLUTION_LOG = Path(os.getenv("EVOLUTION_LOG_PATH", "state/evolution_log.jsonl"))
_EVOLUTION_DECISIONS = Path(os.getenv("EVOLUTION_DECISIONS_PATH", "state/evolution_decisions.jsonl"))
_EVOLUTION_TRIGGER = Path(os.getenv("EVOLUTION_TRIGGER_PATH", "state/evolution_trigger.json"))
_APPROVED_HYPERPARAMS = Path(os.getenv("APPROVED_HYPERPARAMS_PATH", "state/approved_hyperparams.json"))
_DASHBOARD_API_KEY = os.getenv("LUMINA_DASHBOARD_API_KEY", "")

def set_observability_service(obs: Any) -> None:
    """Inject the shared ObservabilityService instance at app startup."""
    global _obs_service
    _obs_service = obs

def set_security_module(sec: dict[str, Any] | None) -> None:
    """Inject the shared security module dict from ``app.py`` (API keys, audit, config)."""
    global _SECURITY_MODULE
    _SECURITY_MODULE = sec

def _load_proposals() -> list[dict[str, Any]]:
    """Return all entries with status=='proposed' from the evolution log."""
    if not _EVOLUTION_LOG.exists():
        return []
    proposals: list[dict[str, Any]] = []
    with _EVOLUTION_LOG.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry: dict[str, Any] = json.loads(raw)
                if entry.get("status") == "proposed":
                    proposals.append(entry)
            except json.JSONDecodeError:
                pass
    return proposals

def _load_decisions() -> dict[str, dict[str, Any]]:
    """Return all decisions keyed by proposal hash."""
    if not _EVOLUTION_DECISIONS.exists():
        return {}
    decisions: dict[str, dict[str, Any]] = {}
    with _EVOLUTION_DECISIONS.open("r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entry: dict[str, Any] = json.loads(raw)
                h = entry.get("entry_hash")
                if h:
                    decisions[str(h)] = entry
            except json.JSONDecodeError:
                pass
    return decisions

def _append_decision(record: dict[str, Any]) -> None:
    """Append a single decision record to the decisions audit log."""
    _EVOLUTION_DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    get_audit_logger().register_stream("evolution.decisions", _EVOLUTION_DECISIONS)
    get_audit_logger().append(
        stream="evolution.decisions",
        payload=record,
        path=_EVOLUTION_DECISIONS,
        mode=_runtime_mode(),
        actor_id="evolution_endpoints",
        severity="info",
    )

def _runtime_mode() -> str:
    raw = os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or os.getenv("LUMINA_RUNTIME_MODE") or "sim"
    return str(raw).strip().lower() or "sim"

def _require_dashboard_key_for_mode() -> bool:
    return _runtime_mode() in {"real", "paper", "sim_real_guard"}

def _verify_legacy_dashboard_key(x_api_key: Optional[str]) -> None:
    if _require_dashboard_key_for_mode() and not _DASHBOARD_API_KEY:
        raise HTTPException(status_code=503, detail="Dashboard API key missing in protected mode")
    if not _DASHBOARD_API_KEY:
        return
    if not x_api_key or x_api_key != _DASHBOARD_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

def _verify_with_security_module(
    x_api_key: Optional[str],
    *,
    require_admin: bool,
) -> dict[str, Any]:
    sec = _SECURITY_MODULE
    if sec is None:
        raise HTTPException(status_code=503, detail="Security module not initialized")
    audit = sec.get("audit_log")
    if not x_api_key:
        if audit is not None and hasattr(audit, "log_auth_attempt"):
            audit.log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="API key required")
    api_key = sec.get("api_key")
    if api_key is None or not hasattr(api_key, "verify_api_key"):
        raise HTTPException(status_code=503, detail="API key authenticator unavailable")
    meta = api_key.verify_api_key(x_api_key)
    if not meta:
        if audit is not None and hasattr(audit, "log_auth_attempt"):
            audit.log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")
    if audit is not None and hasattr(audit, "log_auth_attempt"):
        audit.log_auth_attempt(meta.get("name", "api_key"), True, "api_key")
    cfg = sec.get("config")
    admin_required = bool(getattr(cfg, "admin_role_required", True)) if cfg is not None else True
    if require_admin and admin_required:
        role = str(meta.get("role", "user"))
        if role != "admin":
            if audit is not None and hasattr(audit, "log_unauthorized_access"):
                audit.log_unauthorized_access(
                    meta.get("name", "unknown"),
                    "evolution_mutation",
                    f"insufficient_role_{role}",
                )
            raise HTTPException(status_code=403, detail="Admin role required for evolution mutations")
    return {"api_key": x_api_key, "metadata": meta}

def _verify_api_key(x_api_key: Optional[str], *, require_admin: bool = False) -> None:
    """Authenticate evolution routes; uses injected security or legacy dashboard key."""
    if not _require_dashboard_key_for_mode():
        return
    if _SECURITY_MODULE is not None:
        _verify_with_security_module(x_api_key, require_admin=require_admin)
        return
    _verify_legacy_dashboard_key(x_api_key)
