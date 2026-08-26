"""Birth thread start/stop and historical data preflight."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Dict


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
from lumina_core.birth.progress import read_birth_progress, write_birth_progress
from lumina_launcher.services.birth_runner_lock import (
    clear_runner_lock,
    clear_stale_runner_lock,
    write_runner_lock,
)
from lumina_launcher.services.birth_status_enricher import (
    adaptive_intelligence_status,
    launcher_setup_status,
)

logger = get_logger(__name__)


def _demote_fixed_residuals(svc: Any) -> None:
    """Best-effort: clear known-fixed hard residuals before promising start."""
    try:
        from lumina_launcher.services.birth_residual_cleanup import (
            demote_fixed_birth_residuals,
        )

        result = demote_fixed_birth_residuals(svc.workspace_root)
        if result.get("changed"):
            logger.info("birth.residual.demoted %s", result)
    except Exception as exc:
        logger.debug("birth.residual.demote_failed: %s", exc)


def skip_launcher_history_preflight(
    *,
    force: bool,
    practice_mode: bool,
    continue_training: bool,
    reuse_data: bool,
    checkpoint_exists: bool,
    certified_cache_exists: bool = False,
) -> bool:
    """Whether launcher may skip live Fabric/NT history probe before engine start.

    Fresh certified starts still probe. Resume/reuse with an on-disk checkpoint
    trusts engine cache + fail-closed cold load — no second parallel data gate.
    Certified tick-cache + ``reuse_data`` (no checkpoint) is the Stage-1 physics
    restart path: history is already on disk, so AMBER Fabric must not block.
    """
    if practice_mode:
        return True
    if force:
        return False
    if checkpoint_exists and (continue_training or reuse_data):
        return True
    return bool(reuse_data and certified_cache_exists and not continue_training)


def _checkpoint_resume_ack_metrics(svc: Any) -> tuple[int, int, str]:
    """Return (cumulative_trades, ppo_steps, curriculum_stage) from checkpoint if any."""
    try:
        from lumina_core.birth.checkpoint import load_checkpoint_state

        state = load_checkpoint_state(svc.workspace_root)
        trades = max(0, int(state.get("cumulative_trades", 0) or 0))
        steps = max(0, int(state.get("ppo_steps", 0) or 0))
        stage = str(state.get("curriculum_stage", "") or "").strip()
        return trades, steps, stage
    except Exception:
        return 0, 0, ""


def clear_birth_pause_flags(svc: Any) -> list[str]:
    """Remove cooperative stop flags so resume cannot instantly re-pause.

    Engine ``_stop_requested()`` is true when ``first_boot_pause_requested`` exists.
    Stale flags after user pause are the #1 cause of 'Resume' returning immediately
    to "Birth Phase gepauzeerd door gebruiker."
    """
    root = Path(getattr(svc, "workspace_root", Path.cwd()))
    candidates: list[Path] = []
    pause = getattr(svc, "pause_flag_path", None)
    if pause is not None:
        candidates.append(Path(pause))
    candidates.extend(
        [
            root / "state" / "first_boot_pause_requested",
            root / "state" / "birth_pause.flag",
            root / "state" / "lumina_birth_pause.flag",
        ]
    )
    cleared: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file():
                path.unlink()
                cleared.append(str(path))
        except OSError as exc:
            logger.warning("birth.clear_pause_flag_failed path=%s err=%s", path, exc)
    if cleared:
        logger.info("birth.pause_flags_cleared count=%s paths=%s", len(cleared), cleared)
    return cleared


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
    # Always clear pause flags before any path (fresh or resume) — fail open for start.
    clear_birth_pause_flags(svc)
    # Demote known-fixed hard residuals (e.g. UnboundLocal write_birth_progress) before UI/start.
    _demote_fixed_residuals(svc)

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
    try:
        from lumina_core.birth.tick_cache_persist import certified_tick_cache_present

        certified_cache_exists = certified_tick_cache_present(svc.workspace_root)
    except Exception:
        certified_cache_exists = False
    skip_history_preflight = skip_launcher_history_preflight(
        force=bool(force),
        practice_mode=bool(practice_mode),
        continue_training=bool(continue_training),
        reuse_data=bool(reuse_data),
        checkpoint_exists=bool(checkpoint_exists),
        certified_cache_exists=bool(certified_cache_exists),
    )

    # Elon: fail before promise — sync history preflight BEFORE returning "started".
    # Avoids UI flash Birth→Genesis when Fabric is down. Resume/skip still defers to engine.
    history_preflight_passed = bool(practice_mode or skip_history_preflight)
    if not practice_mode and not skip_history_preflight:
        try:
            write_birth_progress(
                svc.workspace_root,
                stage="pipeline_boot",
                phase="holdout_preflight",
                message="Verifying market history via Execution Fabric…",
                progress_pct=1.0,
                cumulative_trades=0,
                target_trades=int(resolved_target),
                ppo_steps=0,
                birth_start_time=float(svc._start_time or time.time()),
                training_mode="certified",
                user_initiated_stop=False,
                needs_attention=False,
            )
        except Exception as ack_exc:
            logger.warning("birth.start_preflight_progress_failed: %s", ack_exc)
        logger.info(
            "birth.start.sync_history_preflight days=%s workspace=%s",
            resolved_max_real_days,
            svc.workspace_root,
        )
        preflight_ok, preflight_msg = preflight_historical_data(
            svc, resolved_max_real_days
        )
        if not preflight_ok:
            detail = (
                preflight_msg
                or "Historische data niet beschikbaar voor certified training."
            )
            svc._error = detail
            try:
                write_birth_progress(
                    svc.workspace_root,
                    stage="error",
                    phase="loading_history_failed",
                    message=detail,
                    progress_pct=0.0,
                    cumulative_trades=0,
                    target_trades=int(resolved_target),
                    ppo_steps=0,
                    birth_start_time=float(svc._start_time or 0.0),
                    needs_attention=True,
                    retryable=True,
                    last_error=detail,
                    attention_reason_code="history_unavailable",
                    training_mode="certified",
                    residual_failure=True,
                    attention_recommended_actions=[
                        "check_fabric_nt8",
                        "test_connection",
                        "retry_birth",
                    ],
                )
            except Exception as progress_exc:
                logger.warning("birth.preflight_progress_write_failed: %s", progress_exc)
            logger.warning("Birth preflight rejected (sync, no started): %s", detail)
            return {
                "status": "history_unavailable",
                "message": detail,
                "target_trades": resolved_target,
                "max_real_days": resolved_max_real_days,
                "prefer_real_data_only": resolved_prefer_real_data_only,
                "practice_mode": False,
                "continue_training": bool(continue_training),
                "retryable": True,
            }
        history_preflight_passed = True

    # Acknowledge start only after preflight (or skip path) so UI never lies.
    try:
        ack_trades = 0
        ack_ppo = 0
        if skip_history_preflight and checkpoint_exists and not practice_mode:
            ack_trades, ack_ppo, ckpt_stage = _checkpoint_resume_ack_metrics(svc)
            stage_label = ckpt_stage or "curriculum"
            write_birth_progress(
                svc.workspace_root,
                stage="detected",
                phase="checkpoint_resume",
                message=(
                    f"Checkpoint hervatten — {stage_label}, {ack_ppo:,} PPO steps "
                    "(curriculum gaat verder)."
                ),
                progress_pct=2.0,
                cumulative_trades=ack_trades,
                target_trades=int(resolved_target),
                ppo_steps=ack_ppo,
                birth_start_time=float(svc._start_time or time.time()),
                training_mode="certified",
                user_initiated_stop=False,
                needs_attention=False,
                resumed=True,
            )
        else:
            write_birth_progress(
                svc.workspace_root,
                stage="pipeline_boot",
                phase="holdout_preflight" if not practice_mode else "policy_init",
                message=(
                    "History preflight OK — starting Birth Phase…"
                    if not practice_mode
                    else "Birth Phase start — practice mode"
                ),
                progress_pct=2.0,
                cumulative_trades=0,
                target_trades=int(resolved_target),
                ppo_steps=0,
                birth_start_time=float(svc._start_time or time.time()),
                training_mode="practice" if practice_mode else "certified",
                user_initiated_stop=False,
                needs_attention=False,
            )
    except Exception as ack_exc:
        logger.warning("birth.start_ack_progress_failed: %s", ack_exc)

    logger.info("birth.launcher_setup %s", launcher_setup_status(svc))

    def _run_birth() -> None:
        clear_stale_runner_lock(svc)
        write_runner_lock(svc)
        try:
            logger.info(
                "birth.start route=local target_trades=%s max_real_days=%s prefer_real_data_only=%s "
                "practice_mode=%s continue_training=%s reuse_data=%s reuse_existing_policy=%s "
                "skip_history_preflight=%s history_preflight_passed=%s workspace=%s intelligence_tier=%s",
                resolved_target,
                resolved_max_real_days,
                resolved_prefer_real_data_only,
                bool(practice_mode),
                bool(continue_training),
                bool(reuse_data),
                bool(reuse_existing_policy),
                bool(skip_history_preflight),
                bool(history_preflight_passed),
                svc.workspace_root,
                adaptive_intelligence_status(svc).get("tier", "light"),
            )
            # Sync preflight already passed for certified fresh starts.
            # Resume/skip still trusts engine cache + fail-closed cold load.
            if skip_history_preflight and not practice_mode:
                logger.info(
                    "birth.start.skip_launcher_history_preflight continue_training=%s reuse_data=%s",
                    bool(continue_training),
                    bool(reuse_data),
                )
            elif not history_preflight_passed and not practice_mode:
                # Defense-in-depth only (should not run when sync path is used).
                preflight_ok, preflight_msg = preflight_historical_data(
                    svc, resolved_max_real_days
                )
                if not preflight_ok:
                    detail = (
                        preflight_msg
                        or "Historische data niet beschikbaar voor certified training."
                    )
                    svc._error = detail
                    try:
                        write_birth_progress(
                            svc.workspace_root,
                            stage="error",
                            phase="loading_history_failed",
                            message=detail,
                            progress_pct=0.0,
                            cumulative_trades=0,
                            target_trades=int(resolved_target),
                            ppo_steps=0,
                            birth_start_time=float(svc._start_time or 0.0),
                            needs_attention=True,
                            retryable=True,
                            last_error=detail,
                            attention_reason_code="history_unavailable",
                            training_mode="certified",
                        )
                    except Exception as progress_exc:
                        logger.warning(
                            "birth.preflight_progress_write_failed: %s", progress_exc
                        )
                    logger.warning("Birth preflight rejected: %s", detail)
                    return

            previous_cfg = os.getenv("LUMINA_CONFIG", "")
            previous_cwd = Path.cwd()
            os.environ["LUMINA_CONFIG"] = str((svc.workspace_root / "config.yaml").resolve())
            try:
                os.chdir(svc.workspace_root)
                try:
                    from lumina_core.engine.engine_config_helpers import clear_yaml_config_cache

                    clear_yaml_config_cache()
                except Exception:
                    pass
                container = ApplicationContainer()
                _bind_headless_runtime_app(container)
                # Correct poisoned broker_live_provider (yaml SSOT = ninjatrader).
                try:
                    from lumina_launcher.services.birth_runner_preflight import (
                        _resolve_live_provider_from_yaml,
                    )

                    yaml_lp = _resolve_live_provider_from_yaml(Path(svc.workspace_root))
                    if yaml_lp in {"ninjatrader", "nt", "fabric"}:
                        for obj in (getattr(container, "config", None), getattr(container.engine, "config", None)):
                            if obj is not None and str(
                                getattr(obj, "broker_live_provider", "") or ""
                            ).strip().lower() not in {"ninjatrader", "nt", "fabric"}:
                                obj.broker_live_provider = yaml_lp
                except Exception:
                    logger.debug("birth.start.provider_override_failed", exc_info=True)
                ppo_trainer = getattr(container, "ppo_trainer", None)
                if ppo_trainer is None:
                    ppo_trainer = getattr(container.engine, "ppo_trainer", None)
                if not callable(getattr(ppo_trainer, "create_fresh_birth_policy", None)):
                    raise RuntimeError(
                        "PPO trainer unbound or incompatible (missing create_fresh_birth_policy); "
                        "birth cannot mint a policy. Ensure ApplicationContainer wires "
                        "lumina_core.ppo_trainer.PPOTrainer before starting Birth."
                    )
                effective_settings = dict(saved_settings)
                effective_settings["training_trades"] = int(resolved_target)
                engine = LuminaBirthEngine(
                    runtime=container.engine,
                    ppo_trainer=ppo_trainer,
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
            detail = f"{type(e).__name__}: {e}"
            svc._error = detail
            logger.exception("Birth Phase failed: %s", detail)
            # Persist durable error progress so UI matches Telegram after in-memory
            # svc._error is cleared by a later start/restart.
            try:
                prev = read_birth_progress(svc.workspace_root) or {}
                write_birth_progress(
                    svc.workspace_root,
                    stage="error",
                    phase="error",
                    message=detail,
                    progress_pct=float(prev.get("progress_pct", 0) or 0),
                    cumulative_trades=int(
                        prev.get("cumulative_trades", prev.get("trades_done", 0)) or 0
                    ),
                    target_trades=int(prev.get("target_trades", 0) or 0),
                    ppo_steps=int(prev.get("ppo_steps", 0) or 0),
                    birth_start_time=float(prev.get("birth_start_time", 0) or 0),
                    needs_attention=True,
                    retryable=True,
                    last_error=detail,
                    attention_reason_code="birth_error",
                    attention_recommended_actions=[
                        "check_fabric_nt8",
                        "check_mds_connection",
                        "resume_from_checkpoint",
                        "wipe_and_retry",
                    ],
                )
            except Exception as progress_exc:
                logger.warning("birth.error_progress_write_failed: %s", progress_exc)
            try:
                from lumina_core.notifications.attention_events import birth_error_event
                from lumina_core.notifications.operator_notifier import notify_problem

                notify_problem(
                    birth_error_event(detail=detail),
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

from lumina_launcher.services.birth_runner_preflight import load_saved_birth_settings, preflight_historical_data, stop_birth  # noqa: F401, E402
