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
    decision_window: int = 200,
    series_limit: int = 30,
) -> dict[str, Any]:
    """Twin training + durable observability (agreement series, calibration, mode progress)."""
    _verify_api_key(x_api_key, require_admin=False)
    out = _service().metrics(
        decision_window=max(1, min(2000, int(decision_window))),
        series_limit=max(1, min(90, int(series_limit))),
    )
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


@router.get("/discipline")
async def twin_discipline(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """H4: Twin training discipline + high-conf primary readiness (birth/SIM)."""
    _verify_api_key(x_api_key, require_admin=False)
    status = _service().mode_status()
    # mode_status may already embed discipline from controller
    if isinstance(status.get("discipline"), dict):
        out = dict(status["discipline"])
        out["mode_status"] = {
            "mode": status.get("mode"),
            "readiness": status.get("readiness"),
        }
        out.setdefault("local_only", True)
        return out
    from lumina_core.evolution.twin_discipline import discipline_snapshot

    metrics = status.get("metrics") if isinstance(status.get("metrics"), dict) else {}
    out = discipline_snapshot(
        twin_mode=str(status.get("mode") or "shadow"),
        capital_mode=str(status.get("capital_mode_hint") or "sim"),
        metrics=metrics,
        readiness=status.get("readiness") if isinstance(status.get("readiness"), dict) else {},
        auto_promote_when_ready=bool(status.get("auto_promote_when_ready")),
        auto_promote_full_auto=bool(status.get("auto_promote_full_auto_when_ready")),
    )
    out["local_only"] = True
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


from lumina_os.backend.twin_endpoints_auth import (  # noqa: E402,F401
    _require_dashboard_key_for_mode,
    _runtime_mode,
    _service,
    _verify_api_key,
    _verify_legacy_dashboard_key,
    _verify_with_security_module,
    set_security_module,
)
from lumina_os.backend.twin_endpoints_gym import (  # noqa: E402
    twin_gym_answer,
    twin_gym_complete,
    twin_gym_session,
)

# Re-bind FastAPI routes for gym handlers extracted to twin_endpoints_gym.
twin_gym_session = router.post("/gym/session")(twin_gym_session)
twin_gym_answer = router.post("/gym/answer")(twin_gym_answer)
twin_gym_complete = router.post("/gym/complete")(twin_gym_complete)
