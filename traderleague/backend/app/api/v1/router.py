from fastapi import APIRouter

from app.api.v1.routes import health, lumina, rankings, replay

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(lumina.router, prefix="/lumina", tags=["lumina"])
api_router.include_router(rankings.router, prefix="/rankings", tags=["rankings"])
api_router.include_router(replay.router, prefix="/replay", tags=["replay"])
