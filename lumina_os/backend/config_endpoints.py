"""Post-birth bot configuration API (YAML-only updates)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.setup_endpoints import _services
from lumina_launcher.core.onboarding import extract_config_defaults
from lumina_launcher.services.bot_config_persist import persist_bot_config

router = APIRouter(prefix="/api/config", tags=["config"])


class BotConfigRisk(BaseModel):
    kelly_fraction: float = Field(default=1.0, ge=0.05, le=1.0)
    daily_loss_cap: float | None = None
    max_total_open_risk: float = Field(default=3000.0, ge=50.0)
    real_capital_safety_threshold_usd: float = Field(default=1000.0, ge=100.0)


class BotConfigEvolution(BaseModel):
    approval_required: bool = True
    aggressive_evolution: bool = False
    max_mutation_depth: Literal["conservative", "moderate", "radical"] = "conservative"


class BotConfigPreferences(BaseModel):
    instrument: str = Field(default="ES", min_length=1, max_length=16)
    voice_enabled: bool = True
    screen_share_enabled: bool = True
    dashboard_enabled: bool = True
    runtime_trace: bool = True
    runtime_trace_interval_sec: int = Field(default=2, ge=0, le=10)
    latency_sla_ms: int = Field(default=300, ge=150, le=1000)


class BotConfigRequest(BaseModel):
    mode: str = "sim"
    risk: BotConfigRisk = Field(default_factory=BotConfigRisk)
    evolution: BotConfigEvolution = Field(default_factory=BotConfigEvolution)
    preferences: BotConfigPreferences = Field(default_factory=BotConfigPreferences)


@router.post("/bot")
async def save_bot_config(body: BotConfigRequest) -> dict[str, object]:
    _, config_manager, _, _, _, _ = _services()
    try:
        persist_bot_config(
            config_manager=config_manager,
            mode_selection=body.mode,
            risk=body.risk.model_dump(),
            evolution=body.evolution.model_dump(),
            preferences=body.preferences.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    config = config_manager.load_yaml_config()
    env_values = config_manager.parse_env_file()
    return {
        "success": True,
        "defaults": extract_config_defaults(config, env_values=env_values),
    }
