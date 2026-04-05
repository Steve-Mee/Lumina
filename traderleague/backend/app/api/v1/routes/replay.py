from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.traderleague import TradeReplayOut
from app.services.metrics import fetch_trade_replay

router = APIRouter()


@router.get("/trade/{trade_id}", response_model=TradeReplayOut)
def trade_replay(trade_id: int, db: Session = Depends(get_db)) -> TradeReplayOut:
    row = fetch_trade_replay(db, trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    return TradeReplayOut(**row)
