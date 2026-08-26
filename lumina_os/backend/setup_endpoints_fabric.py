"""Setup fabric/configure endpoints (M5)."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

import os
from typing import Literal

from lumina_launcher.services.setup_persist import (
    persist_tauri_quick_config,
    scan_missing_credentials,
)
from lumina_os.backend.setup_onboarding_payload import (
    _services,
    _workspace_root,
    build_onboarding_payload,
)

logger = logging.getLogger(__name__)

class ConfigureCredentials(BaseModel):
    LUMINA_JWT_SECRET_KEY: str = ""
    CROSSTRADE_TOKEN: str = ""
    CROSSTRADE_ACCOUNT: str = ""
    LUMINA_ADMIN_API_KEY: str = ""
    LUMINA_FABRIC_TOKEN: str = ""
    XAI_API_KEY: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    emergency_market_data_fallback: bool = False

class ConfigureRisk(BaseModel):
    kelly_fraction: float = Field(default=1.0, ge=0.05, le=1.0)
    daily_loss_cap: float | None = None
    max_total_open_risk: float = Field(default=3000.0, ge=50.0)
    real_capital_safety_threshold_usd: float = Field(default=1000.0, ge=100.0)

class ConfigureEvolution(BaseModel):
    approval_required: bool = True
    aggressive_evolution: bool = False
    max_mutation_depth: Literal["conservative", "moderate", "radical"] = "conservative"

class ConfigureTraining(BaseModel):
    training_trades: int = Field(default=25000, ge=1000, le=2_000_000)
    prefer_real_data_only: bool = True
    max_real_days: int = Field(default=365, ge=90, le=3650)
    allow_minimal_synthetic_fallback: bool = False
    require_real_simulator_data: bool = True
    stage1_winrate_pass_threshold: float | None = Field(default=None, ge=0.35, le=0.45)

class ConfigureRequest(BaseModel):
    mode: str = "sim"
    credentials: ConfigureCredentials = Field(default_factory=ConfigureCredentials)
    risk: ConfigureRisk = Field(default_factory=ConfigureRisk)
    evolution: ConfigureEvolution = Field(default_factory=ConfigureEvolution)
    training: ConfigureTraining = Field(default_factory=ConfigureTraining)
    selected_model_key: str | None = None

class FabricConnectionTestRequest(BaseModel):
    include_safe_mode: bool = True
    # Empty → diagnostics resolve trading.instrument from config.yaml (e.g. MES SEP26).
    instrument: str = Field(default="", max_length=64)

async def fabric_connection_test(body: FabricConnectionTestRequest | None = None) -> dict[str, Any]:
    """Run SIM-only Execution Fabric diagnostics (Brain ↔ NT8 Fabric, not CrossTrade)."""
    from lumina_launcher.services.fabric_connection_diagnostics import (
        run_fabric_connection_diagnostics,
    )
    from lumina_launcher.services.fabric_link_certificate import write_certificate
    from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

    req = body or FabricConnectionTestRequest()
    # Preserve contract month/year; do not force bare root symbols.
    instrument = str(req.instrument or "").strip()
    # Heal env↔fabric.json before diagnostics so Test connection cannot dual-lie
    # (host GREEN + brain stale token RED).
    try:
        sec = fabric_secret_read(heal=True)
        token_ssot = {
            "token": sec.token,
            "source": sec.source,
            "mismatch": sec.mismatch,
            "healed_process_env": sec.healed,
            "env_len": sec.env_len,
            "json_len": sec.json_len,
            "fingerprint": sec.fingerprint,
            "surfaces_aligned": sec.surfaces_aligned,
        }
    except Exception:
        token_ssot = {}
    try:
        report = run_fabric_connection_diagnostics(
            include_safe_mode=bool(req.include_safe_mode),
            instrument=instrument,
        )
    except Exception as exc:
        logger.exception("fabric-connection-test failed")
        raise HTTPException(status_code=500, detail=f"Fabric diagnostics failed: {exc}") from exc
    payload = report.to_dict()
    if token_ssot:
        payload["token_ssot"] = {
            "source": token_ssot.get("source"),
            "mismatch": token_ssot.get("mismatch"),
            "healed_process_env": token_ssot.get("healed_process_env"),
            "env_len": token_ssot.get("env_len"),
            "json_len": token_ssot.get("json_len"),
        }
    certified = False
    if str(payload.get("overall", "")).lower() == "green":
        token = str(
            (token_ssot or {}).get("token")
            or os.getenv("LUMINA_FABRIC_TOKEN")
            or os.getenv("LUMINA_NT8_API_KEY")
            or ""
        ).strip()
        write_certificate(
            overall="green",
            target=str(payload.get("target") or ""),
            token=token,
            workspace_root=_workspace_root(),
        )
        certified = True
    payload["certified"] = certified
    return payload

async def fabric_bootstrap() -> dict[str, Any]:
    """Zero-touch token + fabric.json + AddOn deploy (idempotent)."""
    from lumina_launcher.services.fabric_bootstrap import run_fabric_bootstrap
    from lumina_launcher.services.fabric_link_certificate import (
        is_halt_active,
        read_certificate,
        read_halt,
    )
    from lumina_launcher.services.fabric_link_health import build_fabric_link_health

    _, config_manager, _, _, _, _ = _services()
    root = _workspace_root()
    result = run_fabric_bootstrap(root, config_manager)
    # Live SSOT — never report fabric_link_green from paper cert alone.
    health = build_fabric_link_health(workspace_root=root, live={})
    result["fabric_link_green"] = bool(health.get("green"))
    result["fabric_link_reason"] = str(health.get("reason") or health.get("meaning") or "")
    result["host_ready"] = bool(health.get("host_ready"))
    result["gate_birth_ok"] = bool(health.get("gate_birth_ok"))
    result["level"] = str(health.get("level") or "RED")
    result["proof"] = health.get("proof") or {}
    result["certificate"] = read_certificate(root)
    result["halt"] = read_halt(root) if is_halt_active(root) else None
    return result

async def fabric_link_status() -> dict[str, Any]:
    """SSOT Fabric link health (live level ≠ paper certificate).

    ``green`` is live GREEN only (Brain session / supervisor auth + host up).
    ``host_ready`` is host running + port (AMBER or GREEN or RESTARTING).
    ``gate_birth_ok`` requires host_ready + recent dual-plane proof.
    ``proof`` is diagnostic certification (never alone drives primary green).

    Cold-start: when supervisor reports AUTH_FAILED, dual-write token SSOT and
    force one reconnect so host hot-reload + Brain SSOT can seal GREEN without
    a full NT restart (see FabricConfig.ResolveToken).
    """
    from lumina_launcher.services.fabric_link_health import build_fabric_link_health

    root = _workspace_root()
    live: dict[str, Any] = {}
    eng: Any = None
    try:
        from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
            ensure_fabric_link_supervisor,
            get_fabric_link_supervisor,
        )
        from lumina_core.engine.engine_config import EngineConfig
        from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

        # Kick always-on supervisor when ninjatrader is configured (status poll = keep-alive).
        eng = EngineConfig()
        # Heal env from fabric.json before supervisor poll (stale env dual-truth).
        try:
            live_tok = str(fabric_secret_read(heal=True).token or "").strip()
        except Exception:
            live_tok = ""
        if live_tok:
            try:
                object.__setattr__(eng, "ninjatrader_nt8_api_key", live_tok)
            except Exception:
                try:
                    eng.ninjatrader_nt8_api_key = live_tok  # type: ignore[attr-defined]
                except Exception:
                    pass

        provider = str(getattr(eng, "broker_live_provider", "") or "").strip().lower()
        if provider in {"ninjatrader", "nt", "fabric"}:
            ensure_fabric_link_supervisor(eng, mode_context="sim")
        live = get_fabric_link_supervisor().status().to_dict()

        # AUTH_FAILED / empty token: dual-write SSOT + reconnect once (Systems Go path).
        err_code = str(live.get("last_error_code") or "").strip().upper()
        if (
            provider in {"ninjatrader", "nt", "fabric"}
            and not live.get("auth_ok")
            and err_code in {"AUTH_FAILED", "TOKEN_EMPTY", "AUTH_TIMEOUT", ""}
        ):
            try:
                from lumina_launcher.services.fabric_link_ensure import (
                    ensure_fabric_token_aligned_and_live,
                )

                _, config_manager, _, _, _, _ = _services()
                ensure_fabric_token_aligned_and_live(
                    config_manager=config_manager,
                    engine_config=eng,
                    workspace_root=root,
                    mode_context="sim",
                    connect_timeout_seconds=6.0,
                    start_supervisor=True,
                )
                live = get_fabric_link_supervisor().status().to_dict()
            except Exception:
                logger.debug("fabric_link_status.token_align_failed", exc_info=True)
    except Exception:
        live = {}

    health = build_fabric_link_health(
        workspace_root=root,
        live=live,
        invalidate_on_host_down=True,
    )
    # Flat fields preserved for existing clients + full health nested.
    return {
        "green": bool(health.get("green")),
        "host_ready": bool(health.get("host_ready")),
        "gate_birth_ok": bool(health.get("gate_birth_ok")),
        "gate_reason": str(health.get("gate_reason") or ""),
        "level": str(health.get("level") or "RED"),
        "meaning": str(health.get("meaning") or ""),
        "reason": str(health.get("reason") or ""),
        "proof": health.get("proof") or {},
        "host": health.get("host") or {},
        "certificate": health.get("certificate"),
        "halt": health.get("halt"),
        "live": health.get("live") or live,
        "health": health,
    }

async def fabric_nt_watch() -> dict[str, Any]:
    """Detect NT8 binary changes and re-probe Fabric (fail-closed halt on failure)."""
    from lumina_launcher.services.ninjatrader_watch import check_ninjatrader_update_and_reprobe

    return check_ninjatrader_update_and_reprobe(_workspace_root())


class FabricHealRequest(BaseModel):
    """Zero-IT repair / first-install pipeline.

    close_ninjatrader defaults to False: auto/soft callers must not kill NT.
    Explicit Repair UI must pass close_ninjatrader=true.
    """

    close_ninjatrader: bool = False
    launch_ninjatrader: bool = True
    run_diagnostic: bool = True
    allow_simhost: bool = False
    force_redeploy: bool = True
    wait_host_sec: float = Field(default=90.0, ge=15.0, le=300.0)


async def fabric_heal(body: FabricHealRequest | None = None) -> dict[str, Any]:
    """Close NT if needed, redeploy bridge, build Custom, launch, wait, dual-plane test."""
    from lumina_launcher.services.fabric_heal import run_fabric_heal

    req = body or FabricHealRequest()
    _, config_manager, _, _, _, _ = _services()
    root = _workspace_root()
    try:
        report = run_fabric_heal(
            root,
            config_manager,
            close_nt=bool(req.close_ninjatrader),
            launch_ninjatrader_flag=bool(req.launch_ninjatrader),
            run_diagnostic=bool(req.run_diagnostic),
            allow_simhost=bool(req.allow_simhost),
            force_redeploy=bool(req.force_redeploy),
            wait_host_sec=float(req.wait_host_sec),
        )
    except Exception as exc:
        logger.exception("fabric-heal failed")
        raise HTTPException(status_code=500, detail=f"Fabric heal failed: {exc}") from exc
    return report.to_dict()

async def configure_setup(body: ConfigureRequest) -> dict[str, Any]:
    setup, config_manager, first_boot, _, hardware, model_service = _services()
    root = _workspace_root()

    missing = scan_missing_credentials(config_manager)
    creds = body.credentials.model_dump()
    for key in ("LUMINA_JWT_SECRET_KEY", "LUMINA_FABRIC_TOKEN"):
        if not str(creds.get(key, "")).strip() and key in missing:
            # process env may satisfy FABRIC token after bootstrap
            if key == "LUMINA_FABRIC_TOKEN" and str(os.getenv("LUMINA_FABRIC_TOKEN", "") or "").strip():
                continue
            if key == "LUMINA_JWT_SECRET_KEY":
                raise HTTPException(status_code=400, detail=f"Missing required credential: {key}")

    snapshot = hardware.get_snapshot(refresh=True)
    # Ensure Vault emergency flag rides configure path (not credentials-only).
    if "emergency_market_data_fallback" not in creds:
        creds["emergency_market_data_fallback"] = bool(
            getattr(body.credentials, "emergency_market_data_fallback", False)
        )
    steps = persist_tauri_quick_config(
        workspace_root=root,
        setup_service=setup,
        config_manager=config_manager,
        first_boot_manager=first_boot,
        model_service=model_service,
        snapshot=snapshot,
        mode_selection=body.mode,
        credentials=creds,
        risk=body.risk.model_dump(),
        evolution=body.evolution.model_dump(),
        training=body.training.model_dump(),
        selected_model_key=body.selected_model_key,
    )
    failures = [s for s in steps if not s.get("success")]
    return {
        "success": not failures,
        "steps": steps,
        "onboarding": build_onboarding_payload(serving_request=True),
    }

class TauriSigningRequest(BaseModel):
    force: bool = False

async def generate_tauri_signing(body: TauriSigningRequest | None = None) -> dict[str, Any]:
    from lumina_launcher.services.tauri_signing_service import TauriSigningService

    _, config_manager, _, _, _, _ = _services()
    service = TauriSigningService(_workspace_root())
    result = service.generate_keypair(
        config_manager=config_manager,
        force=bool(body.force if body else False),
    )
    payload = result.to_dict()
    if not result.success:
        raise HTTPException(status_code=422, detail=result.message)
    return payload
