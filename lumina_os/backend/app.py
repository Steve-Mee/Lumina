"""Thin FastAPI create-app shell for the LUMINA OS backend."""
from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app_auth import check_rate_limit, configure_app_security, verify_admin_role, verify_api_key
from backend.app_lifespan import app_lifespan
from backend.birth_endpoints import router as birth_router
from backend.community_endpoints import configure_community_security
from backend.community_endpoints import router as community_router
from backend.config_endpoints import router as config_router
from backend.core_websocket import router as core_ws_router
from backend.core_websocket import set_observability_service as set_core_ws_obs_service
from backend.embedded_ui import LuminaEmbeddedUIMiddleware, embedded_ui_dist_dir
from backend.emergency_order_endpoints import configure_emergency_security
from backend.emergency_order_endpoints import router as emergency_router
from backend.evolution_endpoints import router as evolution_router
from backend.evolution_endpoints import set_observability_service as set_evolution_obs_service
from backend.evolution_endpoints import set_security_module as set_evolution_security_module
from backend.maturity_endpoints import router as maturity_router
from backend.monitoring_endpoints import router as monitoring_router, set_observability_service
from backend.ninjatrader_websocket import router as ninjatrader_ws_router
from backend.notifications_endpoints import router as notifications_router
from backend.ppo_websocket import router as ppo_ws_router
from backend.runtime_endpoints import router as runtime_router
from backend.setup_endpoints import router as setup_router
from backend.twin_endpoints import router as twin_router
from backend.twin_endpoints import set_security_module as set_twin_security_module
from lumina_core.monitoring import ObservabilityService
from lumina_core.security import get_security_module
from lumina_launcher.services.birth_service import configure_birth_workspace

logger = logging.getLogger(__name__)

_LUMINA_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Ensure backend sees the same env as launcher/runtime.
load_dotenv(_LUMINA_REPO_ROOT / ".env")
load_dotenv()

configure_birth_workspace(_LUMINA_REPO_ROOT)

# Load config
CONFIG_PATH = os.getenv("LUMINA_CONFIG", "config.yaml")
with open(CONFIG_PATH, "r") as f:
    FULL_CONFIG = yaml.safe_load(f)
SECURITY_CONFIG = FULL_CONFIG.get("security", {})

# Initialize security module
SECURITY = get_security_module(SECURITY_CONFIG)
set_evolution_security_module(SECURITY)
set_twin_security_module(SECURITY)
configure_app_security(SECURITY)
configure_emergency_security(SECURITY)
configure_community_security(SECURITY)

# Validate dangerous configs at startup
validator = SECURITY["config_validator"]
violations = validator.validate(FULL_CONFIG)
if violations:
    logger.error(f"Dangerous config values detected: {violations}")
    raise ValueError(f"Startup validation failed: {violations}")

_UI_DIST = embedded_ui_dist_dir()

app = FastAPI(title="Trader League Live - Powered by LUMINA", lifespan=app_lifespan)

# ── Observability layer ────────────────────────────────────────────────────────
_obs = ObservabilityService.from_config(FULL_CONFIG)
_obs.start()
set_observability_service(_obs)
set_core_ws_obs_service(_obs)
set_evolution_obs_service(_obs)
app.include_router(monitoring_router)
app.include_router(evolution_router)
app.include_router(twin_router)
app.include_router(birth_router)
app.include_router(maturity_router)
app.include_router(notifications_router)
app.include_router(setup_router)
app.include_router(config_router)
app.include_router(runtime_router)
app.include_router(core_ws_router)
app.include_router(ppo_ws_router)
app.include_router(ninjatrader_ws_router)
app.include_router(emergency_router)
app.include_router(community_router)

app.add_middleware(LuminaEmbeddedUIMiddleware, dist_dir=_UI_DIST)
if (_UI_DIST / "index.html").is_file():
    logger.info("Embedded React monitoring UI served under /ui from %s", _UI_DIST)
else:
    logger.info(
        "Embedded React UI not present at %s; GET /ui returns 503 until built "
        "(cd frontend && npm ci && npm run build:embedded)",
        _UI_DIST,
    )

# Apply strict CORS middleware (no wildcard) + lokale Vite dev (:5173) origins
try:
    from api.monitoring import extend_cors_origins_with_local_vite_dev

    cors_origins = extend_cors_origins_with_local_vite_dev(SECURITY["config"].cors_allowed_origins)
except ImportError:  # pragma: no cover
    cors_origins = list(SECURITY["config"].cors_allowed_origins)

if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PUT", "OPTIONS"],
        allow_headers=["*"],
    )
    logger.info(
        "CORS configured for %s origins (Vite :5173 merged via api.monitoring when available)",
        len(cors_origins),
    )
else:
    logger.warning("CORS is disabled (allow_origins is empty)")

# Re-exports for tests that import from app
__all__ = [
    "app",
    "verify_api_key",
    "verify_admin_role",
    "check_rate_limit",
    "LuminaEmbeddedUIMiddleware",
]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
