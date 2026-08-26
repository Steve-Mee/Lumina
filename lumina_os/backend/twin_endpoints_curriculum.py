"""Twin base curriculum, micro training, and escalation endpoints (ADR-0037)."""

from __future__ import annotations

import logging
from typing import Any, Literal, Optional

from fastapi import Header, HTTPException, Path
from pydantic import BaseModel, Field

from lumina_os.backend.twin_endpoints_auth import _service, _verify_api_key

logger = logging.getLogger(__name__)


class TwinBaseStartRequest(BaseModel):
    model_config = {"extra": "forbid"}

    force_restart: bool = False


class TwinBaseAnswerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    question_id: str
    choice_id: str
    clarify: str = Field(default="", max_length=280)
    session_id: str | None = None
    train_now: bool = True


class TwinMicroStartRequest(BaseModel):
    model_config = {"extra": "forbid"}

    count: int = Field(default=3, ge=1, le=5)
    prefer_historical: bool = True
    dual_channel: bool = True
    notify_telegram: bool = True


class TwinMicroAnswerRequest(BaseModel):
    model_config = {"extra": "forbid"}

    pending_id: str
    choice_id: str
    clarify: str = Field(default="", max_length=280)
    resolve_token: str | None = None
    train_now: bool = True


class TwinEscalationCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}

    dna_hash: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    explanation: str = ""
    twin_recommendation: bool | None = None
    notify_telegram: bool = True


class TwinEscalationResolveRequest(BaseModel):
    model_config = {"extra": "forbid"}

    choice_id: str
    clarify: str = Field(default="", max_length=280)
    resolve_token: str | None = None
    resolved_by: Literal["deck", "telegram", "api", "cli"] = "deck"
    train_now: bool = True


async def twin_base_start(
    body: TwinBaseStartRequest | None = None,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Start app-only base training curriculum (≤12 min, forced-choice)."""
    _verify_api_key(x_api_key, require_admin=True)
    req = body or TwinBaseStartRequest()
    try:
        return _service().start_base_training(force_restart=bool(req.force_restart))
    except Exception as exc:
        logger.exception("twin base start failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_base_status(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    return _service().base_training_status()


async def twin_base_next(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    return _service().next_base_question()


async def twin_base_answer(
    body: TwinBaseAnswerRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    try:
        return _service().submit_base_answer(
            question_id=body.question_id,
            choice_id=body.choice_id,
            clarify=body.clarify,
            session_id=body.session_id,
            train_now=bool(body.train_now),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin base answer failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_base_complete(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    try:
        return _service().complete_base_training(train_batch=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin base complete failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_readiness(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Birth-ready flag + base completion for Phase Hub."""
    _verify_api_key(x_api_key, require_admin=False)
    out = _service().readiness()
    try:
        m = _service().metrics(decision_window=50, series_limit=7)
        out["escalation_rate"] = m.get("escalation_rate")
        out["avg_prediction_error"] = m.get("avg_prediction_error")
        out["mode"] = m.get("mode")
        out["autonomy_resolution_pct"] = m.get("autonomy_resolution_pct")
    except Exception:
        pass
    return out


async def twin_micro_start(
    body: TwinMicroStartRequest | None = None,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    req = body or TwinMicroStartRequest()
    try:
        return _service().start_micro_session(
            count=int(req.count),
            prefer_historical=bool(req.prefer_historical),
            dual_channel=bool(req.dual_channel),
            notify_telegram=bool(req.notify_telegram),
        )
    except Exception as exc:
        logger.exception("twin micro start failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_micro_answer(
    body: TwinMicroAnswerRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    try:
        return _service().submit_micro(
            pending_id=body.pending_id,
            choice_id=body.choice_id,
            clarify=body.clarify,
            resolved_by="deck",
            resolve_token=body.resolve_token,
            train_now=bool(body.train_now),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin micro answer failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_escalations_pending(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=False)
    items = _service().list_pending_escalations()
    return {"items": items, "count": len(items), "local_only": True}


async def twin_escalation_create(
    body: TwinEscalationCreateRequest,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    try:
        out = _service().create_escalation(
            dna_hash=body.dna_hash,
            confidence=float(body.confidence),
            risk_flags=list(body.risk_flags or []),
            explanation=body.explanation,
            twin_recommendation=body.twin_recommendation,
            notify_telegram=bool(body.notify_telegram),
        )
        # Never return resolve_token on public admin create unless needed — strip for safety
        out.pop("resolve_token", None)
        return out
    except Exception as exc:
        logger.exception("twin escalation create failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def twin_escalation_resolve(
    body: TwinEscalationResolveRequest,
    escalation_id: str = Path(...),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _verify_api_key(x_api_key, require_admin=True)
    try:
        return _service().resolve_escalation(
            escalation_id,
            choice_id=body.choice_id,
            clarify=body.clarify,
            resolved_by=body.resolved_by,
            resolve_token=body.resolve_token,
            train_now=bool(body.train_now),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("twin escalation resolve failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class TwinDecisionFeedbackRequest(BaseModel):
    model_config = {"extra": "forbid"}

    action: Literal["OK", "A", "V", "M", "approve", "reject", "modify", "FIX_A", "FIX_V", "FIX_M"]
    notes: str = Field(default="", max_length=280)
    train_now: bool = True


async def twin_decisions_recent(
    limit: int = 20,
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Recent Twin judgments (operator feed) for Deck parity with Telegram."""
    _verify_api_key(x_api_key, require_admin=False)
    from lumina_core.evolution.twin_decision_notify import get_decision_notify_store

    items = get_decision_notify_store().list_recent(limit=max(1, min(100, int(limit))))
    return {"items": items, "count": len(items), "local_only": True}


async def twin_decision_feedback(
    body: TwinDecisionFeedbackRequest,
    decision_id: str = Path(...),
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Operator feedback on a Twin decision → Steve label + online RLHF."""
    _verify_api_key(x_api_key, require_admin=True)
    from lumina_core.evolution.twin_decision_notify import apply_decision_feedback

    act = str(body.action).strip().upper()
    if act in {"APPROVE"}:
        act = "A"
    elif act in {"REJECT", "VETO"}:
        act = "V"
    elif act in {"MODIFY"}:
        act = "M"
    try:
        return apply_decision_feedback(
            decision_id,
            action=act,
            notes=body.notes,
            resolved_by="deck",
            train_now=bool(body.train_now),
        )
    except Exception as exc:
        logger.exception("twin decision feedback failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
