from datetime import datetime

from fastapi import APIRouter

from app.schemas.traderleague import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", service="traderleague-api", timestamp=datetime.utcnow())
