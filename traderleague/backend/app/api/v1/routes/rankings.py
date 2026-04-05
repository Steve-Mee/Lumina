from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import TimeBucket
from app.schemas.traderleague import ParticipantMetricsOut, RankingOut
from app.services.metrics import fetch_live_metrics, fetch_rankings

router = APIRouter()


@router.get("/live", response_model=list[ParticipantMetricsOut])
def live_metrics(db: Session = Depends(get_db)) -> list[ParticipantMetricsOut]:
    return [ParticipantMetricsOut(**row) for row in fetch_live_metrics(db)]


@router.get("", response_model=list[RankingOut])
def rankings(bucket: TimeBucket = Query(default=TimeBucket.DAILY), db: Session = Depends(get_db)) -> list[RankingOut]:
    rows = fetch_rankings(db, bucket)
    return [RankingOut(**row) for row in rows]
