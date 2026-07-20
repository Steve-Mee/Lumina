"""Birth thread start/stop and historical data preflight."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from lumina_core.container import ApplicationContainer
from lumina_core.engine.runtime_entrypoint import _bind_headless_runtime_app
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_PPO_UPDATE_TIMESTEPS,
    FIRST_BOOT_DEFAULT_TRADES,
    normalize_first_boot_training_trades,
    resolve_default_max_real_days,
)
from lumina_core.logging_utils import get_logger
from lumina_core.birth.engine import BirthPhaseEngineV2 as LuminaBirthEngine  # direct (thin facade deleted for simplicity)
from lumina_core.order_gatekeeper import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_launcher.services.birth_runner_lock import (
    clear_runner_lock,
    clear_stale_runner_lock,
    mark_user_stopped_progress,
    write_runner_lock,
)
from lumina_launcher.services.birth_status_enricher import (
    adaptive_intelligence_status,
    launcher_setup_status,
)
from lumina_launcher.services.birth_status_mapper import BIRTH_ACTIVE_STAGES

logger = get_logger(__name__)


def load_saved_birth_settings(svc: Any) -> dict[str, Any]:
    config_path = svc.workspace_root / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    if not isinstance(cfg, dict):
        return {}
    section = cfg.get("first_boot")
    return section if isinstance(section, dict) else {}


def preflight_historical_data(svc: Any, max_real_days: int) -> tuple[bool, str]:
    """Probe Crosstrade/historical API before certified Birth Phase starts."""
    previous_cfg = os.getenv("LUMINA_CONFIG", "")
    previous_cwd = Path.cwd()
    os.environ["LUMINA_CONFIG"] = str((svc.workspace_root / "config.yaml").resolve())
    try:
        os.chdir(svc.workspace_root)
        container = ApplicationContainer()
        _bind_headless_runtime_app(container)
        mds = container.market_data_service
        if mds is None or not hasattr(mds, "load_historical_ohlc_extended"):
            return False, (
                "Certified Birth Phase vereist MarketDataService.load_historical_ohlc_extended; "
                "service niet beschikbaar."
            )
        rows = mds.load_historical_ohlc_extended(
            days_back=max(1, int(max_real_days)),
            limit=500,
            ticks_per_bar=4,
        )
        if not rows:
            cfg = getattr(container, "config", None)
            instrument = str(getattr(cfg, "instrument", "") or "MES").strip()
            stale_msg = ""
            if instrument and is_stale_contract_symbol(instrument):
                rolled = roll_stale_contract_symbol(instrument)
                stale_msg = (
                    f" Instrument {instrument} is verlopen; probeer {rolled} in config.yaml. "
                    if rolled != instrument.upper()
                    else f" Instrument {instrument} lijkt verlopen. "
                )
            return False, (
                "Geen historische marktdata beschikbaar voor certified training."
                f"{stale_msg}"
                "Controleer Crosstrade credentials (CROSSTRADE_TOKEN), NT8/CrossTrade verbinding en netwerk."
            )
        return True, ""
    except Exception as exc:
        logger.warning("Birth preflight historical data failed: %s", exc, exc_info=True)
        return False, f"Historische data preflight mislukt: {exc}"
    finally:
        os.chdir(previous_cwd)
        if previous_cfg:
            os.environ["LUMINA_CONFIG"] = previous_cfg
        else:
            os.environ.pop("LUMINA_CONFIG", None)


def start_birth(
    svc: Any,
    *,
    target_trades: int | None = None,
    force: bool = False,
    practice_mode: bool = False,
    explicit_user_start: bool = False,
    continue_training: bool = False,
    reuse_data: bool = False,
    expand_data: bool = False,
) -> Dict[str, Any]:
    if not explicit_user_start:
        return {
            "status": "rejected",
            "message": "Birth Phase start requires an explicit user action (Start Birth Phase).",
        }

    if svc.is_running():
        return {"status": "already_running", "message": "Birth Phase is already in progress"}

    if svc.is_completed() and not force and not practice_mode and not continue_training:
        return {"status": "already_completed", "message": "Birth Phase already completed"}

    svc._stop_requested.clear()
    try:
        if svc.pause_flag_path.exists():
            svc.pause_flag_path.unlink()
    except OSError:
        pass

    try:
        from lumina_core.birth.genesis_charter import persist_genesis_charter

        charter = persist_genesis_charter(svc.workspace_root)
        if target_trades is None:
            target_trades = int(charter.training_trades)
    except Exception as exc:
        logger.debug("birth.genesis_charter.persist_failed: %s", exc)

    svc._result = None
    svc._error = None
    svc._start_time = time.time()
    saved_settings = load_saved_birth_settings(svc)
    requested_target = (
        normalize_first_boot_training_trades(target_trades)
        if target_trades is not None
        else 0
    )
    saved_target = normalize_first_boot_training_trades(
        saved_settings.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)
    )
    resolved_target = requested_target or saved_target or FIRST_BOOT_DEFAULT_TRADES
    resolved_max_real_days = int(
        saved_settings.get("max_real_days")
        or resolve_default_max_real_days(resolved_target)
    )
    resolved_prefer_real_data_only = (
        False if practice_mode else bool(saved_settings.get("prefer_real_data_only", True))
    )
    raw_ppo_update_timesteps = saved_settings.get("ppo_update_timesteps", FIRST_BOOT_DEFAULT_PPO_UPDATE_TIMESTEPS)
    try:
        resolved_ppo_update_timesteps = max(1_000, int(raw_ppo_update_timesteps))
    except (TypeError, ValueError):
        resolved_ppo_update_timesteps = FIRST_BOOT_DEFAULT_PPO_UPDATE_TIMESTEPS
    checkpoint_exists = (svc.workspace_root / "state" / "lumina_birth_checkpoint.json").exists() or (
        svc.workspace_root / "state" / "first_boot_checkpoint.json"
    ).exists()
    reuse_existing_policy = bool(continue_training or (checkpoint_exists and not force))

    if not practice_mode:
        preflight_ok, preflight_msg = preflight_historical_data(svc, resolved_max_real_days)
        if not preflight_ok:
            return {
                "status": "rejected",
                "message": preflight_msg or "Historische data niet beschikbaar voor certified training.",
            }

    logger.info("birth.launcher_setup %s", launcher_setup_status(svc))

    def _run_birth() -> None:
        clear_stale_runner_lock(svc)
        write_runner_lock(svc)
        try:
            logger.info(
                "birth.start route=local target_trades=%s max_real_days=%s prefer_real_data_only=%s practice_mode=%s continue_training=%s reuse_existing_policy=%s workspace=%s intelligence_tier=%s",
                resolved_target,
                resolved_max_real_days,
                resolved_prefer_real_data_only,
                bool(practice_mode),
                bool(continue_training),
                bool(reuse_existing_policy),
                svc.workspace_root,
                adaptive_intelligence_status(svc).get("tier", "light"),
            )
            previous_cfg = os.getenv("LUMINA_CONFIG", "")
            previous_cwd = Path.cwd()
            os.environ["LUMINA_CONFIG"] = str((svc.workspace_root / "config.yaml").resolve())
            try:
                os.chdir(svc.workspace_root)
                container = ApplicationContainer()
                _bind_headless_runtime_app(container)
                effective_settings = dict(saved_settings)
                effective_settings["training_trades"] = int(resolved_target)
                engine = LuminaBirthEngine(
                    runtime=container.engine,
                    market_data_service=container.market_data_service,
                    config={"first_boot": effective_settings},
                    workspace_root=svc.workspace_root,
                    stop_event=svc._stop_requested,
                )
                # Explicit Approval Twin bind (ADR-0031/0032): container already
                # constructed EvolutionOrchestrator via bind_evolution_promotion_event_bus.
                # Fail-closed: missing twin is OK (autonomy falls back to notify paths).
                try:
                    from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator

                    twin = getattr(EvolutionOrchestrator(), "_approval_twin", None)
                    if twin is not None:
                        engine.approval_twin = twin
                        engine._approval_twin = twin  # noqa: SLF001 — intentional dual attr
                        if hasattr(engine, "_birth_handler_registry") and hasattr(
                            engine._birth_handler_registry, "bind_approval_twin"
                        ):
                            engine._birth_handler_registry.bind_approval_twin(twin)
                        if hasattr(twin, "bind_event_bus") and getattr(engine, "event_bus", None) is not None:
                            try:
                                twin.bind_event_bus(engine.event_bus)
                            except Exception:
                                logger.debug("birth.twin_bind_event_bus_failed", exc_info=True)
                        twin_mode = str(getattr(twin, "mode", "shadow") or "shadow")
                        logger.info(
                            "birth.twin.bound mode=%s executable=false path=orchestrator",
                            twin_mode,
                        )
                    else:
                        logger.info("birth.twin.unbound reason=orchestrator_missing_twin")
                except Exception:
                    logger.debug("birth.twin.bind_failed", exc_info=True)
                container.register_birth_reload_host(engine)
                container.start_config_hot_reload()
                try:
                    svc._result = engine.run_birth_phase(
                        target_trades=resolved_target,
                        max_real_days=resolved_max_real_days,
                        prefer_real_data_only=resolved_prefer_real_data_only,
                        chunk_size=50000,
                        ppo_update_timesteps=resolved_ppo_update_timesteps,
                        force=force,
                        practice_mode=bool(practice_mode),
                        reuse_existing_policy=bool(reuse_existing_policy),
                        reuse_data_manifest=bool(reuse_data),
                        expand_data=bool(expand_data),
                    )
                finally:
                    container.stop_config_hot_reload()
                    container.clear_birth_reload_host(engine)
            finally:
                os.chdir(previous_cwd)
                if previous_cfg:
                    os.environ["LUMINA_CONFIG"] = previous_cfg
                else:
                    os.environ.pop("LUMINA_CONFIG", None)
            logger.info("Birth Phase completed successfully")
        except Exception as e:
            svc._error = str(e)
            logger.exception("Birth Phase failed: %s", e)
            try:
                from lumina_core.notifications.attention_events import birth_error_event
                from lumina_core.notifications.operator_notifier import notify_problem

                notify_problem(
                    birth_error_event(detail=str(e)),
                    workspace_root=svc.workspace_root,
                )
            except Exception as notify_exc:
                logger.warning("birth.error_attention_failed: %s", notify_exc)
        finally:
            clear_runner_lock(svc)

    svc._thread = threading.Thread(target=_run_birth, daemon=True, name="LuminaBirthThread")
    svc._thread.start()
    svc._stalled_auto_resume_attempted = False

    return {
        "status": "started",
        "target_trades": resolved_target,
        "max_real_days": resolved_max_real_days,
        "prefer_real_data_only": resolved_prefer_real_data_only,
        "practice_mode": bool(practice_mode),
        "continue_training": bool(continue_training),
        "message": (
            "Practice Birth Phase started in background"
            if practice_mode
            else "Birth Phase started in background"
        ),
    }


def stop_birth(svc: Any, join_timeout: float = 15.0) -> Dict[str, Any]:
    """Cooperative stop: signal engine via event + pause flag, optionally join thread."""
    had_thread = svc.is_running()
    progress = svc._load_progress()
    stage = str(progress.get("stage", "") or "").strip().lower()
    progress_active = stage in BIRTH_ACTIVE_STAGES

    if not had_thread and not progress_active and not svc.is_stopping():
        return {"status": "not_running", "message": "Geen actieve Birth Phase."}

    svc._stop_requested.set()
    svc.pause_flag_path.parent.mkdir(parents=True, exist_ok=True)
    svc.pause_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")

    if had_thread and svc._thread is not None:
        svc._thread.join(timeout=max(0.1, float(join_timeout)))
        if svc.is_running():
            mark_user_stopped_progress(svc)
            return {
                "status": "stopping",
                "message": "Birth Phase stop aangevraagd — wacht op checkpoint.",
            }
        mark_user_stopped_progress(svc)
        return {"status": "stopped", "message": "Birth Phase gestopt."}

    if progress_active:
        mark_user_stopped_progress(svc)
        return {
            "status": "stopped",
            "message": "Stop-aanvraag vastgelegd (geen actieve thread in dit proces).",
        }

    return {"status": "stopping", "message": "Birth Phase stop aangevraagd."}