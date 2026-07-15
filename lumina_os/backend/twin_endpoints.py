"""FastAPI endpoints for Approval Twin training (Steve labels + light RLHF).

Endpoints
---------
GET  /api/twin/review-queue   – Recent twin decisions to label
GET  /api/twin/labels         – Auditable SteveValuesRegistry history
POST /api/twin/label          – Record approve/reject/modify + optional RLHF
POST /api/twin/train          – fine_tune_from_registry
GET  /api/twin/metrics        – Twin training / agreement metrics

All training data stays local under state/. Never calls promotion or REAL
capital paths. Auth mirrors evolution_endpoints.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
from lumina_core.evolution.twin_training_service import TwinTrainingService

router = APIRouter(prefix="/api/twin", tags=["twin"])
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


def _service() -> TwinTrainingService:
    registry = SteveValuesRegistry(
        sqlite_path=_REGISTRY_SQLITE,
        jsonl_path=_REGISTRY_JSONL,
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=_MODEL_PATH)
    return TwinTrainingService(
        registry=registry,
        twin=twin,
        model_path=_MODEL_PATH,
        decisions_path=_DECISIONS_PATH,
        training_path=_TRAINING_PATH,
    )


class TwinLabelRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision: Literal["approve", "reject", "modify"]
    dna_hash: str
    notes: str = ""
    twin_score: float | None = None
    twin_recommendation: bool | None = None
    explanation: str = ""
    risk_flags: list[str] = Field(default_factory=list)
    confidence_score: float | None = None
    train_now: bool = True


class TwinTrainRequest(BaseModel):
    model_config = {"extra": "forbid"}

    limit: int = Field(default=250, ge=1, le=5000)


class TwinGymSessionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    count: int = Field(default=4, ge=3, le=5)
    prefer_historical: bool = True


class TwinGymAnswerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    decision: Literal["approve", "reject", "modify"]
    dna_hash: str
    summary: str = ""
    estimated_confidence: float | None = None
    notes: str = ""
    session_id: str | None = None
    train_now: bool = True


class TwinGymAnswerItem(BaseModel):
    model_config = {"extra": "forbid"}

    decision: Literal["approve", "reject", "modify"]
    dna_hash: str
    summary: str = ""
    estimated_confidence: float | None = None
    notes: str = ""


class TwinGymCompleteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    answers: list[TwinGymAnswerItem] = Field(default_factory=list)
    session_id: str | None = None
    train_now: bool = True


@router.get("/review-queue")
async def twin_review_queue(
    limit: int = Query(default=20, ge=1, le=200),
    include_labeled: bool = Query(
        default=False,
        description="If false (default), hide DNA already present in SteveValues registry",
    ),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    svc = _service()
    items = svc.list_review_queue(limit=limit, include_labeled=bool(include_labeled))
    high = sum(1 for i in items if i.get("stakes") == "high")
    return {
        "items": items,
        "count": len(items),
        "high_stakes_count": high,
        "include_labeled": bool(include_labeled),
        "path": str(_DECISIONS_PATH),
        "local_only": True,
    }


@router.get("/labels")
async def twin_labels(
    limit: int = Query(default=50, ge=1, le=500),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    svc = _service()
    labels = svc.list_labels(limit=limit)
    return {
        "labels": labels,
        "count": len(labels),
        "registry_sqlite": str(_REGISTRY_SQLITE),
        "registry_jsonl": str(_REGISTRY_JSONL),
        "local_only": True,
    }


@router.post("/label")
async def twin_label(
    body: TwinLabelRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    dna = str(body.dna_hash or "").strip()
    if not dna:
        raise HTTPException(status_code=400, detail="dna_hash is required")
    svc = _service()
    try:
        result = svc.record_decision(
            decision=body.decision,
            dna_hash=dna,
            notes=body.notes,
            twin_score=body.twin_score,
            twin_recommendation=body.twin_recommendation,
            explanation=body.explanation,
            risk_flags=list(body.risk_flags or []),
            confidence_score=body.confidence_score,
            train_now=bool(body.train_now),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin label failed")
        raise HTTPException(status_code=500, detail=f"Failed to record twin label: {exc}") from exc
    return result


@router.post("/train")
async def twin_train(
    body: TwinTrainRequest | None = None,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    limit = int(body.limit) if body is not None else 250
    svc = _service()
    try:
        return svc.train(limit=limit)
    except Exception as exc:
        logger.exception("twin train failed")
        raise HTTPException(status_code=500, detail=f"Twin train failed: {exc}") from exc


@router.get("/metrics")
async def twin_metrics(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    out = _service().metrics()
    out.setdefault("local_only", True)
    return out


@router.get("/mode")
async def twin_mode(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Current twin judgment mode + promotion readiness (shadow → assisted → full_auto)."""
    _verify_api_key(x_api_key, require_admin=False)
    out = _service().mode_status()
    out.setdefault("local_only", True)
    return out


class TwinPromoteRequest(BaseModel):
    model_config = {"extra": "forbid"}

    target: Literal["assisted", "full_auto", "advisory", "active"]


@router.post("/promote")
async def twin_promote(
    body: TwinPromoteRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Promote twin mode only if measurable gates pass (fail-closed, no criteria bypass)."""
    _verify_api_key(x_api_key, require_admin=True)
    result = _service().promote_mode(body.target)
    if not result.get("promoted"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Twin mode promotion blocked by gate",
                "result": result,
            },
        )
    return result


@router.post("/gym/session")
async def twin_gym_session(
    body: TwinGymSessionRequest | None = None,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Start a practice Approval Gym session (3–5 drills). Does not promote DNA."""
    _verify_api_key(x_api_key, require_admin=False)
    req = body or TwinGymSessionRequest()
    svc = _service()
    try:
        return svc.start_gym_session(
            count=int(req.count),
            prefer_historical=bool(req.prefer_historical),
        )
    except Exception as exc:
        logger.exception("twin gym session failed")
        raise HTTPException(status_code=500, detail=f"Gym session failed: {exc}") from exc


@router.post("/gym/answer")
async def twin_gym_answer(
    body: TwinGymAnswerRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Record one gym answer; practice labels only (local registry + optional RLHF)."""
    _verify_api_key(x_api_key, require_admin=True)
    dna = str(body.dna_hash or "").strip()
    if not dna:
        raise HTTPException(status_code=400, detail="dna_hash is required")
    svc = _service()
    try:
        return svc.record_gym_answer(
            decision=body.decision,
            dna_hash=dna,
            summary=body.summary,
            estimated_confidence=body.estimated_confidence,
            notes=body.notes,
            session_id=body.session_id,
            train_now=bool(body.train_now),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin gym answer failed")
        raise HTTPException(status_code=500, detail=f"Gym answer failed: {exc}") from exc


@router.post("/gym/complete")
async def twin_gym_complete(
    body: TwinGymCompleteRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Batch-complete a gym session with one RLHF pass."""
    _verify_api_key(x_api_key, require_admin=True)
    if not body.answers:
        raise HTTPException(status_code=400, detail="answers list is empty")
    svc = _service()
    try:
        payload = [a.model_dump() for a in body.answers]
        return svc.complete_gym_session(
            answers=payload,
            train_now=bool(body.train_now),
            session_id=body.session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin gym complete failed")
        raise HTTPException(status_code=500, detail=f"Gym complete failed: {exc}") from exc
