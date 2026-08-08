"""Twin gym endpoints (M5)."""
from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from lumina_os.backend.twin_endpoints_auth import _service, _verify_api_key

import logging
logger = logging.getLogger(__name__)
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
