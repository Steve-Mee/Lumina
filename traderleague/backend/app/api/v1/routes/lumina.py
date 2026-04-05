import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_signature
from app.db.session import get_db
from app.models.entities import Participant
from app.schemas.traderleague import PublicLuminaEntryIn, PublicLuminaEntryOut, TradeCloseWebhookIn
from app.services.ingest import ensure_verified_account, upsert_trade_close

router = APIRouter()
settings = get_settings()


@router.post("/entry", response_model=PublicLuminaEntryOut)
def public_lumina_entry(payload: PublicLuminaEntryIn, db: Session = Depends(get_db)) -> PublicLuminaEntryOut:
    if payload.token != settings.lumina_public_entry_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid public entry token")

    existing = db.execute(select(Participant).where(Participant.handle == payload.handle)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Handle already exists")

    api_key_hash = hashlib.sha256(payload.api_key_plain.encode("utf-8")).hexdigest()
    participant = Participant(
        handle=payload.handle,
        display_name=payload.display_name,
        api_key_hash=api_key_hash,
        is_lumina_public=True,
    )
    db.add(participant)
    db.commit()
    db.refresh(participant)

    return PublicLuminaEntryOut(
        participant_id=participant.id,
        handle=participant.handle,
        display_name=participant.display_name,
        is_lumina_public=participant.is_lumina_public,
    )


@router.post("/webhooks/trade-close")
async def on_trade_close(
    request: Request,
    x_lumina_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    body = await request.body()
    if not verify_signature(settings.webhook_shared_secret, body, x_lumina_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = TradeCloseWebhookIn.model_validate_json(body)
    try:
        participant, account = ensure_verified_account(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    trade = upsert_trade_close(db, payload, participant_id=participant.id, account_id=account.id)
    db.commit()
    return {"status": "accepted", "trade_id": trade.id}
