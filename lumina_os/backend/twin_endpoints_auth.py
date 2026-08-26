"""Twin endpoint auth helpers (M5)."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_training_service import TwinTrainingService

logger = logging.getLogger(__name__)

_SECURITY_MODULE: dict[str, Any] | None = None
_DASHBOARD_API_KEY = os.getenv("LUMINA_DASHBOARD_API_KEY", "")

_STATE = Path(os.getenv("LUMINA_STATE_DIR", "state"))
_MODEL_PATH = Path(os.getenv("APPROVAL_TWIN_MODEL_PATH", str(_STATE / "approval_twin_model.json")))
_DECISIONS_PATH = Path(
    os.getenv("TWIN_DECISIONS_PATH", str(_STATE / "monitoring_twin_decisions.jsonl"))
)
_TRAINING_PATH = Path(
    os.getenv("TWIN_TRAINING_PATH", str(_STATE / "monitoring_twin_training.jsonl"))
)
_REGISTRY_SQLITE = Path(
    os.getenv("STEVE_VALUES_SQLITE", str(_STATE / "steve_values_registry.sqlite3"))
)
_REGISTRY_JSONL = Path(
    os.getenv("STEVE_VALUES_JSONL", str(_STATE / "steve_values_registry.jsonl"))
)

def set_security_module(sec: dict[str, Any] | None) -> None:
    """Inject shared security module from app.py (optional)."""
    global _SECURITY_MODULE
    _SECURITY_MODULE = sec

def _runtime_mode() -> str:
    raw = (
        os.getenv("LUMINA_MODE")
        or os.getenv("TRADE_MODE")
        or os.getenv("LUMINA_RUNTIME_MODE")
        or "sim"
    )
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
                    "twin_training_mutation",
                    f"insufficient_role_{role}",
                )
            raise HTTPException(status_code=403, detail="Admin role required for twin training")
    return {"api_key": x_api_key, "metadata": meta}

def _verify_api_key(x_api_key: Optional[str], *, require_admin: bool = False) -> None:
    if not _require_dashboard_key_for_mode():
        return
    if _SECURITY_MODULE is not None:
        _verify_with_security_module(x_api_key, require_admin=require_admin)
        return
    _verify_legacy_dashboard_key(x_api_key)

_SERVICE: TwinTrainingService | None = None
_SERVICE_LOCK = __import__("threading").Lock()


def _service() -> TwinTrainingService:
    """Process-local singleton — avoid rebuilding Twin + registry on every HTTP hit."""
    global _SERVICE
    if _SERVICE is not None:
        return _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is not None:
            return _SERVICE
        registry = SteveValuesRegistry(
            sqlite_path=_REGISTRY_SQLITE,
            jsonl_path=_REGISTRY_JSONL,
        )
        twin = ApprovalTwinAgent(registry=registry, model_path=_MODEL_PATH)
        _SERVICE = TwinTrainingService(
            registry=registry,
            twin=twin,
            model_path=_MODEL_PATH,
            decisions_path=_DECISIONS_PATH,
            training_path=_TRAINING_PATH,
        )
        return _SERVICE
