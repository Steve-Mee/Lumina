#!/usr/bin/env python3
"""
LUMINA BIRTH SERVICE
====================

Production-grade service om de LuminaBirthEngine te starten en te monitoren.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from lumina_core.container import ApplicationContainer
from lumina_core.adaptive_intelligence import AdaptiveIntelligenceManager
from lumina_core.engine.runtime_entrypoint import _bind_headless_runtime_app
from lumina_core.order_gatekeeper import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_core.lumina_birth_engine import LuminaBirthEngine
from lumina_core.first_boot_progress import (
    birth_runner_lock_active,
    birth_training_is_live,
    read_birth_runner_lock,
    resolve_first_boot_stage,
    resolve_progress_active_max_age_sec,
)
from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_PPO_UPDATE_TIMESTEPS,
    FIRST_BOOT_DEFAULT_TRADES,
    normalize_first_boot_training_trades,
    resolve_default_max_real_days,
)
from lumina_core.logging_utils import get_logger
from lumina_launcher.core.setup_gate import launcher_setup_status_payload
from lumina_launcher.services.workspace_root import resolve_birth_workspace_root

logger = get_logger(__name__)
_POLICY_REL = Path("lumina_agents") / "ppo" / "lumina_ppo_policy.zip"
_BIRTH_ACTIVE_STAGES = frozenset(
    {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "historical_loaded",
        "synthetic_top_up",
        "parallel_simulation",
        "ppo_training",
        "deferred_calendar",
        "simulation_stall_retry",
        "curriculum_learning",
        "curriculum_research",
        "data_expansion",
    }
)


def resolve_terminal_birth_status(progress: Dict[str, Any] | None) -> tuple[str, str] | None:
    """Map durable progress terminal phases to top-level API status (SSOT for recovery UI)."""
    if not progress:
        return None
    phase = str(progress.get("phase", "") or "").strip().lower()
    stage_name = str(progress.get("stage", "") or "").strip().lower()

    if phase == "stage_stalled" or stage_name == "stage_stalled":
        message = str(
            progress.get("pass_reason")
            or progress.get("message")
            or "Curriculum stage stalled — metrics did not converge."
        )
        return ("stage_stalled", message)

    if phase in {"certificate_failed", "certificate_remediation"}:
        message = str(
            progress.get("message") or "Birth Certificate v2 thresholds not met."
        )
        return ("certificate_failed", message)

    if stage_name == "failed" and phase == "certificate_failed":
        message = str(
            progress.get("message") or "Birth Certificate v2 thresholds not met."
        )
        return ("certificate_failed", message)

    return None


class BirthService:
    _instance: Optional["BirthService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "BirthService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._thread: Optional[threading.Thread] = None
        self._result: Optional[Dict[str, Any]] = None
        self._error: Optional[str] = None
        self._start_time: Optional[float] = None
        self._stop_requested = threading.Event()
        self._stalled_auto_resume_attempted = False

        self.configure_workspace(resolve_birth_workspace_root())

        self._initialized = True
        logger.info("BirthService initialized (singleton) workspace=%s", self.workspace_root)

    def _launcher_setup_status(self) -> dict[str, Any]:
        try:
            return launcher_setup_status_payload(self.workspace_root)
        except Exception as exc:
            logger.warning("birth.launcher_setup.status_failed detail=%s", exc)
            return {
                "setup_complete": False,
                "intelligence_stack_ready": False,
                "needs_smart_setup": True,
                "needs_guided_setup": False,
                "launcher_ready": False,
                "recommended_model": "",
                "recommended_provider": "ollama",
                "recommended_ollama_tag": "",
                "missing": ["launcher_setup_status_failed"],
            }

    def _enrich_birth_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload["launcher_setup"] = self._launcher_setup_status()
        return payload

    def _adaptive_intelligence_status(self) -> dict[str, Any]:
        try:
            manager = AdaptiveIntelligenceManager(self.workspace_root)
            return manager.to_dict()
        except Exception as exc:
            logger.warning("birth.adaptive_intelligence.status_failed detail=%s", exc)
            return {
                "tier": "light",
                "mode": "auto",
                "reasoning_mode": "fast_path_only",
                "degraded_state": True,
                "status_reason": "adaptive_intelligence_init_failed",
                "recommended_model": "",
                "recommended_provider": "ollama",
                "context_length": 0,
                "last_probe_error": str(exc),
            }

    def configure_workspace(self, workspace_root: Path | str | None = None) -> Path:
        """Bind state paths to repo root (safe when backend cwd != repo root)."""
        resolved = resolve_birth_workspace_root(workspace_root)
        if getattr(self, "workspace_root", None) != resolved:
            self._stalled_auto_resume_attempted = False
        self.workspace_root = resolved
        self.progress_file = self.workspace_root / "state" / "lumina_birth_progress.json"
        self.legacy_progress_file = self.workspace_root / "state" / "first_boot_progress.json"
        self.completed_flag = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.checkpoint_file = self.workspace_root / "state" / "lumina_birth_checkpoint.json"
        self.runner_lock_path = self.workspace_root / "state" / "birth_runner.json"
        self.policy_path = self.workspace_root / _POLICY_REL
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.reconcile_orphaned_birth_progress()
        self._maybe_auto_resume_stalled_birth()
        return self.workspace_root

    def _should_auto_resume_stalled_birth(self, progress: Dict[str, Any]) -> bool:
        if progress.get("user_initiated_stop") is True:
            return False
        if progress.get("retryable") is False:
            return False
        phase = str(progress.get("phase", "") or "").strip().lower()
        if phase in {"plateau_evolution", "stall_remediation", "curriculum_learning"}:
            return self._is_stage_stalled_recovery_eligible()
        if progress.get("needs_attention") is True:
            return False
        terminal = str(progress.get("terminal_stall_reason") or "").strip().lower()
        if terminal in {"plateau_evolution_exhausted", "stall_remediation_exhausted"}:
            return False
        if progress.get("curriculum_integrity_blocked") is True:
            return False
        phase = str(progress.get("phase", "") or "").strip().lower()
        stage = str(progress.get("stage", "") or "").strip().lower()
        if phase != "stage_stalled" and stage != "stage_stalled":
            return False
        return self._is_stage_stalled_recovery_eligible()

    def _curriculum_integrity_audit(self) -> tuple[bool, list[str]]:
        from lumina_core.birth.checkpoint import read_checkpoint_payload
        from lumina_core.birth.config import load_birth_v2_config
        from lumina_core.birth.stage_pass_receipt import audit_curriculum_integrity, parse_stage_pass_receipts

        payload = read_checkpoint_payload(self.workspace_root) or {}
        progress = self._load_progress()
        stages = list(payload.get("stages_passed") or progress.get("stages_passed") or [])
        receipts = parse_stage_pass_receipts(payload.get("stage_pass_receipts"))
        cfg = load_birth_v2_config(self.workspace_root)
        training_mode = str(
            payload.get("training_mode") or progress.get("training_mode") or "certified"
        )
        audit = audit_curriculum_integrity(
            stages_passed=stages,
            stage_pass_receipts=receipts,
            cfg=cfg.curriculum,
            training_mode=training_mode,
        )
        return audit.ok, list(audit.invalid_reasons)

    def _maybe_auto_resume_stalled_birth(self) -> None:
        """Autonomously resume retryable stage_stalled (ADR-0017 never-stop)."""
        if self.is_running() or self._stalled_auto_resume_attempted:
            return
        progress = self._load_progress()
        if not self._should_auto_resume_stalled_birth(progress):
            return
        integrity_ok, integrity_reasons = self._curriculum_integrity_audit()
        if not integrity_ok:
            logger.warning(
                "birth.auto_resume blocked curriculum_integrity reasons=%s",
                integrity_reasons,
            )
            from lumina_core.birth.progress import write_birth_progress

            write_birth_progress(
                self.workspace_root,
                stage=str(progress.get("stage", "stage_stalled") or "stage_stalled"),
                phase=str(progress.get("phase", "stage_stalled") or "stage_stalled"),
                message=(
                    "Auto-resume blocked: curriculum integrity audit failed. "
                    "Retry stage manually after reviewing pass receipts."
                ),
                progress_pct=float(progress.get("progress_pct", 0) or 0),
                cumulative_trades=int(
                    progress.get("cumulative_trades", progress.get("trades_done", 0)) or 0
                ),
                target_trades=int(progress.get("target_trades", 0) or 0),
                ppo_steps=int(progress.get("ppo_steps", 0) or 0),
                birth_start_time=float(progress.get("birth_start_time", 0) or 0),
                curriculum_integrity_blocked=True,
                curriculum_integrity_reasons=integrity_reasons,
                retryable=True,
                needs_attention=True,
            )
            try:
                from lumina_core.notifications.attention_events import curriculum_integrity_blocked_event
                from lumina_core.notifications.attention_notifier import notify_attention

                notify_attention(
                    curriculum_integrity_blocked_event(reasons=integrity_reasons),
                    workspace_root=self.workspace_root,
                )
            except Exception as exc:
                logger.warning("birth.integrity_attention_failed: %s", exc)
            return
        self._stalled_auto_resume_attempted = True
        logger.info("birth.auto_resume stage_stalled initiating resume_stalled_stage")
        result = self.resume_stalled_stage()
        status = str(result.get("status", "") or "").strip().lower()
        logger.info("birth.auto_resume stage_stalled result=%s", status or "unknown")
        if status in {"started", "already_running"}:
            self._stalled_auto_resume_attempted = False

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_requested

    def artifacts_ok(self) -> bool:
        from lumina_core.birth.birth_certificate import validate_certificate_artifacts
        from lumina_core.birth.config import load_birth_v2_config

        thresholds = load_birth_v2_config(self.workspace_root).certificate_thresholds
        ok, _reason, _cert = validate_certificate_artifacts(
            self.workspace_root,
            thresholds=thresholds,
        )
        return ok and self.policy_path.is_file()

    def certificate_ok(self) -> bool:
        from lumina_core.birth.birth_certificate import validate_certificate_artifacts
        from lumina_core.birth.config import load_birth_v2_config

        thresholds = load_birth_v2_config(self.workspace_root).certificate_thresholds
        ok, _reason, _cert = validate_certificate_artifacts(
            self.workspace_root,
            thresholds=thresholds,
        )
        return ok

    def _load_saved_birth_settings(self) -> dict[str, Any]:
        config_path = self.workspace_root / "config.yaml"
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

    def _preflight_historical_data(self, max_real_days: int) -> tuple[bool, str]:
        """Probe Crosstrade/historical API before certified Birth Phase starts."""
        previous_cfg = os.getenv("LUMINA_CONFIG", "")
        previous_cwd = Path.cwd()
        os.environ["LUMINA_CONFIG"] = str((self.workspace_root / "config.yaml").resolve())
        try:
            os.chdir(self.workspace_root)
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
        self,
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

        if self.is_running():
            return {"status": "already_running", "message": "Birth Phase is already in progress"}

        if self.is_completed() and not force and not practice_mode and not continue_training:
            return {"status": "already_completed", "message": "Birth Phase already completed"}

        self._stop_requested.clear()
        try:
            if self.pause_flag_path.exists():
                self.pause_flag_path.unlink()
        except OSError:
            pass

        self._result = None
        self._error = None
        self._start_time = time.time()
        saved_settings = self._load_saved_birth_settings()
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
        checkpoint_exists = (self.workspace_root / "state" / "lumina_birth_checkpoint.json").exists() or (
            self.workspace_root / "state" / "first_boot_checkpoint.json"
        ).exists()
        reuse_existing_policy = bool(continue_training or (checkpoint_exists and not force))

        if not practice_mode:
            preflight_ok, preflight_msg = self._preflight_historical_data(resolved_max_real_days)
            if not preflight_ok:
                return {
                    "status": "rejected",
                    "message": preflight_msg or "Historische data niet beschikbaar voor certified training.",
                }

        logger.info("birth.launcher_setup %s", self._launcher_setup_status())

        def _run_birth() -> None:
            self._clear_stale_runner_lock()
            self._write_runner_lock()
            try:
                logger.info(
                    "birth.start route=local target_trades=%s max_real_days=%s prefer_real_data_only=%s practice_mode=%s continue_training=%s reuse_existing_policy=%s workspace=%s intelligence_tier=%s",
                    resolved_target,
                    resolved_max_real_days,
                    resolved_prefer_real_data_only,
                    bool(practice_mode),
                    bool(continue_training),
                    bool(reuse_existing_policy),
                    self.workspace_root,
                    self._adaptive_intelligence_status().get("tier", "light"),
                )
                previous_cfg = os.getenv("LUMINA_CONFIG", "")
                previous_cwd = Path.cwd()
                os.environ["LUMINA_CONFIG"] = str((self.workspace_root / "config.yaml").resolve())
                try:
                    os.chdir(self.workspace_root)
                    container = ApplicationContainer()
                    _bind_headless_runtime_app(container)
                    effective_settings = dict(saved_settings)
                    effective_settings["training_trades"] = int(resolved_target)
                    engine = LuminaBirthEngine(
                        runtime=container.engine,
                        market_data_service=container.market_data_service,
                        config={"first_boot": effective_settings},
                        workspace_root=self.workspace_root,
                        stop_event=self._stop_requested,
                    )
                    self._result = engine.run_birth_phase(
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
                    os.chdir(previous_cwd)
                    if previous_cfg:
                        os.environ["LUMINA_CONFIG"] = previous_cfg
                    else:
                        os.environ.pop("LUMINA_CONFIG", None)
                logger.info("Birth Phase completed successfully")
            except Exception as e:
                self._error = str(e)
                logger.exception("Birth Phase failed: %s", e)
            finally:
                self._clear_runner_lock()

        self._thread = threading.Thread(target=_run_birth, daemon=True, name="LuminaBirthThread")
        self._thread.start()
        self._stalled_auto_resume_attempted = False

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

    def _sanitize_running_progress(self, progress: Dict[str, Any]) -> Dict[str, Any]:
        """Drop stale failure phases while a birth run is actively executing."""
        sanitized = dict(progress)
        phase = str(sanitized.get("phase", "") or "").strip().lower()
        if phase in {"curriculum_failed", "simulation_stall"}:
            sanitized["phase"] = "curriculum_learning"
            sanitized["stage"] = "training_running"
        birth_start = float(sanitized.get("birth_start_time", 0) or 0)
        if birth_start > 0:
            start_sec = birth_start / 1000.0 if birth_start > 1e12 else birth_start
            sanitized["elapsed_sec"] = round(max(0.0, time.time() - start_sec), 2)
        return sanitized

    def _resolve_elapsed_seconds_from_progress(self, progress: Dict[str, Any]) -> float:
        birth_start = float(progress.get("birth_start_time", 0) or 0)
        if birth_start > 0:
            start_sec = birth_start / 1000.0 if birth_start > 1e12 else birth_start
            return round(max(0.0, time.time() - start_sec), 1)
        elapsed = float(progress.get("elapsed_sec", 0) or 0)
        return round(elapsed, 1) if elapsed > 0 else 0.0

    def _is_stage_stalled_recovery_eligible(self) -> bool:
        progress = self._load_progress()
        terminal = resolve_terminal_birth_status(progress)
        if terminal is not None and terminal[0] == "stage_stalled":
            return True
        from lumina_core.birth.checkpoint import load_checkpoint_state

        checkpoint_state = load_checkpoint_state(self.workspace_root)
        ckpt_phase = str(checkpoint_state.get("phase", "") or "").strip().lower()
        progress_phase = str(progress.get("phase", "") or "").strip().lower()
        recoverable_phases = {"stage_stalled", "plateau_evolution", "stall_remediation"}
        if ckpt_phase in recoverable_phases:
            return True
        return progress_phase in recoverable_phases

    def get_status(self) -> Dict[str, Any]:
        self._maybe_auto_resume_stalled_birth()
        progress = self._load_progress()
        terminal = resolve_terminal_birth_status(progress)
        if terminal is not None and not self.is_running():
            terminal_status, terminal_message = terminal
            live = birth_training_is_live(self.workspace_root, thread_running=False)
            return self._enrich_birth_status(
                {
                    "progress": progress,
                    "live": live,
                    "status": terminal_status,
                    "progress_pct": float(progress.get("progress_pct", 0) or 0),
                    "message": terminal_message,
                    "result": self._result,
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if self.is_running() or self._progress_indicates_running(progress):
            progress = self._sanitize_running_progress(progress)
        live = birth_training_is_live(self.workspace_root, thread_running=self.is_running())
        stage = resolve_first_boot_stage(progress)
        base_meta = {"progress": progress, "live": live}

        if self._error:
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": "error",
                    "error": self._error,
                    "message": "Birth Phase gefaald",
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if self.is_running():
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": "running",
                    "runner": "thread",
                    "elapsed_seconds": round(time.time() - self._start_time, 1) if self._start_time else 0,
                    "message": "Birth Phase draait...",
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if self._progress_indicates_running(progress):
            runner_meta = self._read_runner_lock() or {}
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": "running",
                    "runner": str(runner_meta.get("runner", "file_progress")),
                    "message": str(progress.get("message") or "Birth Phase actief (cross-process)."),
                    "runner_pid": runner_meta.get("pid"),
                    "runner_host": runner_meta.get("host"),
                    "elapsed_seconds": self._resolve_elapsed_seconds_from_progress(progress),
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if self.completed_flag.exists():
            cert_ok = self.certificate_ok()
            if not cert_ok:
                phase = str(progress.get("phase", "") or "").lower()
                stage_name = str(progress.get("stage", "") or "").lower()
                if phase == "certificate_failed" or stage_name == "failed":
                    status = "certificate_failed"
                    message = str(
                        progress.get("message") or "Birth Certificate v2 thresholds not met."
                    )
                else:
                    status = "certificate_failed"
                    message = (
                        "Birth completion flag present but Birth Certificate v2 is missing or invalid."
                    )
                return self._enrich_birth_status(
                    {
                        **base_meta,
                        "status": status,
                        "progress_pct": float(progress.get("progress_pct", 100) or 100),
                        "message": message,
                        "result": self._result,
                        "orphaned": False,
                        "adaptive_intelligence": self._adaptive_intelligence_status(),
                    }
                )
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": "completed",
                    "progress_pct": 100,
                    "message": "Birth Phase complete",
                    "result": self._result,
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if stage == "interrupted":
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": "interrupted",
                    "orphaned": True,
                    "message": str(
                        progress.get("message")
                        or "Vorige Birth Phase gestopt. Klik Start Birth Phase om opnieuw te beginnen."
                    ),
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        terminal = resolve_terminal_birth_status(progress)
        if terminal is not None:
            terminal_status, terminal_message = terminal
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": terminal_status,
                    "progress_pct": float(progress.get("progress_pct", 0) or 0),
                    "message": terminal_message,
                    "result": self._result,
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )

        if isinstance(self._result, dict) and self._result and self._progress_is_persisted():
            status = str(self._result.get("status", "idle") or "idle")
            msg = str(progress.get("message") or self._result.get("message") or "Birth Phase klaar.")
            return self._enrich_birth_status(
                {
                    **base_meta,
                    "status": status,
                    "result": self._result,
                    "message": msg,
                    "orphaned": False,
                    "adaptive_intelligence": self._adaptive_intelligence_status(),
                }
            )
        return self._enrich_birth_status(
            {
                **base_meta,
                "status": "idle",
                "message": "Birth Phase nog niet gestart",
                "orphaned": False,
                "adaptive_intelligence": self._adaptive_intelligence_status(),
            }
        )

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_stopping(self) -> bool:
        return self._stop_requested.is_set()

    def stop_birth(self, join_timeout: float = 5.0) -> Dict[str, Any]:
        """Cooperative stop: signal engine via event + pause flag, optionally join thread."""
        had_thread = self.is_running()
        progress = self._load_progress()
        stage = str(progress.get("stage", "") or "").strip().lower()
        progress_active = stage in _BIRTH_ACTIVE_STAGES

        if not had_thread and not progress_active and not self.is_stopping():
            return {"status": "not_running", "message": "Geen actieve Birth Phase."}

        self._stop_requested.set()
        self.pause_flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.pause_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")

        if had_thread and self._thread is not None:
            self._thread.join(timeout=max(0.1, float(join_timeout)))
            if self.is_running():
                return {
                    "status": "stopping",
                    "message": "Birth Phase stop aangevraagd — wacht op checkpoint.",
                }
            self._mark_user_stopped_progress()
            return {"status": "stopped", "message": "Birth Phase gestopt."}

        if progress_active:
            self._mark_user_stopped_progress()
            return {
                "status": "stopped",
                "message": "Stop-aanvraag vastgelegd (geen actieve thread in dit proces).",
            }

        return {"status": "stopping", "message": "Birth Phase stop aangevraagd."}

    def wipe_all_birth_data(self, *, join_timeout: float = 30.0) -> Dict[str, Any]:
        """Stop active birth (if any) and remove all birth training artifacts."""
        stop_result = self._ensure_birth_stopped_for_wipe(join_timeout=join_timeout)
        if stop_result is not None:
            return stop_result

        from lumina_launcher.core.birth_reset import clear_birth_training_state

        reset_result = clear_birth_training_state(self.workspace_root)
        self._reset_in_memory_birth_state()
        return {
            "status": "wiped",
            "message": "Alle birth-data verwijderd — klaar voor schone start.",
            "removed_artifacts": reset_result.removed,
        }

    def _progress_is_persisted(self) -> bool:
        return self.progress_file.exists() or self.legacy_progress_file.exists()

    def _reset_in_memory_birth_state(self) -> None:
        self._result = None
        self._error = None
        self._start_time = None
        self._stop_requested.clear()
        self._clear_stale_runner_lock()

    def _ensure_birth_stopped_for_wipe(self, *, join_timeout: float) -> Dict[str, Any] | None:
        """Stop birth thread; return error payload if still running after join."""
        if self.is_running() or self.is_stopping():
            self.stop_birth(join_timeout=join_timeout)
        if self.is_running():
            return {
                "status": "rejected",
                "message": (
                    "Birth Phase kon niet volledig stoppen — probeer opnieuw na enkele seconden "
                    "of herstart de backend."
                ),
            }
        return None

    def _wipe_birth_training_artifacts(self, *, join_timeout: float = 30.0) -> Dict[str, Any] | None:
        """Shared wipe for genesis wipe-all and retry(wipe=True). Returns error dict on failure."""
        stop_result = self._ensure_birth_stopped_for_wipe(join_timeout=join_timeout)
        if stop_result is not None:
            return stop_result
        from lumina_launcher.core.birth_reset import clear_birth_training_state

        clear_birth_training_state(self.workspace_root)
        self._reset_in_memory_birth_state()
        return None

    def is_completed(self) -> bool:
        if not self.completed_flag.exists():
            return False
        return self.certificate_ok()

    def retry_birth(self, target_trades: int | None = None, *, wipe: bool = False) -> Dict[str, Any]:
        """Resume from checkpoint on certificate failure; wipe only when explicitly requested."""
        from lumina_core.birth.config import BRO_ENGINE_VERSION
        from lumina_core.birth.checkpoint import load_checkpoint_state
        from lumina_core.birth.remediation import (
            reconstruct_checkpoint_from_progress,
            should_fast_path_remediation_from_state,
        )

        progress = self._load_progress()
        phase = str(progress.get("phase", "") or "").strip().lower()
        checkpoint_state = load_checkpoint_state(self.workspace_root)
        checkpoint_exists = (
            self.checkpoint_file.exists()
            or (self.workspace_root / "state" / "first_boot_checkpoint.json").exists()
        )
        fast_path_eligible = (
            should_fast_path_remediation_from_state(progress, checkpoint_state) if not wipe else False
        )
        preserve_checkpoint = not wipe and fast_path_eligible
        if preserve_checkpoint and not checkpoint_exists:
            policy_hint = str(self.policy_path) if self.policy_path.exists() else ""
            reconstructed = reconstruct_checkpoint_from_progress(
                self.workspace_root,
                progress,
                policy_path=policy_hint,
                checkpoint=checkpoint_state,
            )
            if not reconstructed:
                logger.warning(
                    "birth.retry reconstruct_failed phase=%s policy_exists=%s",
                    phase,
                    self.policy_path.exists(),
                )
                preserve_checkpoint = False
            checkpoint_exists = (
                self.checkpoint_file.exists()
                or (self.workspace_root / "state" / "first_boot_checkpoint.json").exists()
            )
        logger.info(
            "birth.retry preserve_checkpoint=%s phase=%s checkpoint_exists=%s wipe=%s "
            "fast_path_eligible=%s engine_version=%s",
            preserve_checkpoint,
            phase,
            checkpoint_exists,
            wipe,
            fast_path_eligible,
            BRO_ENGINE_VERSION,
        )
        if wipe:
            wipe_error = self._wipe_birth_training_artifacts()
            if wipe_error is not None:
                return wipe_error
        elif not preserve_checkpoint:
            from lumina_launcher.core.first_boot import FirstBootManager

            FirstBootManager(self.workspace_root).clear_stale_for_certified_retry()
        return self.start_birth(
            target_trades=target_trades,
            force=not preserve_checkpoint,
            explicit_user_start=True,
            continue_training=preserve_checkpoint,
        )

    def resume_stalled_stage(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Resume curriculum from terminal stage_stalled without wiping checkpoint."""
        from lumina_core.birth.checkpoint import reset_adaptation_budget_for_manual_resume

        if not self._is_stage_stalled_recovery_eligible():
            return {
                "status": "rejected",
                "message": "Resume stage requires stage_stalled progress or checkpoint.",
            }
        reset_adaptation_budget_for_manual_resume(self.workspace_root)
        return self.start_birth(
            target_trades=target_trades,
            force=False,
            explicit_user_start=True,
            continue_training=True,
        )

    def expand_and_retry_stalled_stage(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Expand historical data window then resume stalled stage (no checkpoint wipe)."""
        from lumina_core.birth.checkpoint import (
            read_checkpoint_payload,
            reset_adaptation_budget_for_manual_resume,
            write_checkpoint_payload,
        )

        if not self._is_stage_stalled_recovery_eligible():
            return {
                "status": "rejected",
                "message": "Expand and retry requires stage_stalled progress or checkpoint.",
            }
        reset_adaptation_budget_for_manual_resume(self.workspace_root)
        payload = read_checkpoint_payload(self.workspace_root)
        if payload:
            metrics = dict(payload.get("stage_metrics") or {})
            metrics["pending_data_expand"] = True
            payload["stage_metrics"] = metrics
            payload["phase"] = "curriculum_learning"
            write_checkpoint_payload(self.workspace_root, payload)
        return self.start_birth(
            target_trades=target_trades,
            force=False,
            explicit_user_start=True,
            continue_training=True,
            reuse_data=True,
            expand_data=True,
        )

    def resume_birth(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Non-destructive resume from the last birth checkpoint."""
        return self.start_birth(
            target_trades=target_trades,
            force=False,
            explicit_user_start=True,
            continue_training=True,
        )

    def reuse_data_birth(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Resume checkpoint and skip holdout preflight expansion when manifest hash matches."""
        return self.start_birth(
            target_trades=target_trades,
            force=False,
            explicit_user_start=True,
            continue_training=True,
            reuse_data=True,
        )

    def reset_birth(self) -> None:
        for f in [self.completed_flag, self.checkpoint_file]:
            if f.exists():
                f.unlink()
        logger.warning("Birth Phase state reset (development only)")

    def _load_progress(self) -> Dict[str, Any]:
        if self.progress_file.exists():
            try:
                with open(self.progress_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "trades_done": 0,
            "target_trades": FIRST_BOOT_DEFAULT_TRADES,
            "progress_pct": 0,
            "ppo_steps": 0,
            "stage": "not_started",
        }

    def _progress_timestamp_age_sec(self, progress: Dict[str, Any]) -> float | None:
        raw = str(progress.get("timestamp", "") or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds())
        except Exception:
            return None

    def _mark_user_stopped_progress(self) -> None:
        """Persist interrupted progress with user_initiated_stop so UI skips auto-resume."""
        self._clear_stale_runner_lock()
        progress = self._load_progress()
        stage = resolve_first_boot_stage(progress)
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "interrupted",
            "phase": "restart_required",
            "message": (
                "Birth Phase gestopt door gebruiker. "
                "Kies Start birth of Wis birth-data voor schone run."
            ),
            "target_trades": int(progress.get("target_trades", FIRST_BOOT_DEFAULT_TRADES) or FIRST_BOOT_DEFAULT_TRADES),
            "trades_done": int(progress.get("trades_done", 0) or 0),
            "cumulative_trades": int(progress.get("cumulative_trades", 0) or 0),
            "total_trades": int(progress.get("total_trades", 0) or 0),
            "ppo_steps": int(progress.get("ppo_steps", 0) or 0),
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "prior_stage": stage if stage in _BIRTH_ACTIVE_STAGES else str(progress.get("stage", "") or ""),
            "prior_phase": str(progress.get("phase", "") or ""),
            "user_initiated_stop": True,
        }
        encoded = json.dumps(payload, ensure_ascii=True, indent=2)
        for path in (self.progress_file, self.legacy_progress_file):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(encoded, encoding="utf-8")
            except OSError:
                logger.warning("birth.user_stop.write_failed path=%s", path, exc_info=True)
        try:
            if self.pause_flag_path.exists():
                self.pause_flag_path.unlink()
        except OSError:
            logger.warning("birth.user_stop.pause_clear_failed", exc_info=True)

    def reconcile_orphaned_birth_progress(self) -> bool:
        """Mark on-disk active progress as interrupted when no live Birth runner exists."""
        self._clear_stale_runner_lock()
        progress = self._load_progress()
        phase = str(progress.get("phase", "") or "").strip().lower()
        if phase in {"plateau_evolution", "stall_remediation", "stage_stalled"}:
            return False
        stage = resolve_first_boot_stage(progress)
        if stage not in _BIRTH_ACTIVE_STAGES:
            return False
        if birth_training_is_live(self.workspace_root, thread_running=self.is_running()):
            return False
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "interrupted",
            "phase": "restart_required",
            "message": (
                "Vorige Birth Phase gestopt (herstart). "
                "Klik Start Birth Phase om opnieuw te beginnen."
            ),
            "target_trades": int(progress.get("target_trades", FIRST_BOOT_DEFAULT_TRADES) or FIRST_BOOT_DEFAULT_TRADES),
            "trades_done": int(progress.get("trades_done", 0) or 0),
            "cumulative_trades": int(progress.get("cumulative_trades", 0) or 0),
            "total_trades": int(progress.get("total_trades", 0) or 0),
            "ppo_steps": int(progress.get("ppo_steps", 0) or 0),
            "progress_pct": float(progress.get("progress_pct", 0) or 0),
            "prior_stage": stage,
            "prior_phase": str(progress.get("phase", "") or ""),
            "user_initiated_stop": True,
        }
        encoded = json.dumps(payload, ensure_ascii=True, indent=2)
        for path in (self.progress_file, self.legacy_progress_file):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(encoded, encoding="utf-8")
            except OSError:
                logger.warning("birth.reconcile.write_failed path=%s", path, exc_info=True)
        logger.info("birth.reconcile_orphaned prior_stage=%s workspace=%s", stage, self.workspace_root)
        return True

    def _progress_indicates_running(self, progress: Dict[str, Any]) -> bool:
        if resolve_terminal_birth_status(progress) is not None:
            return False
        phase = str(progress.get("phase", "") or "").strip().lower()
        stage_name = str(progress.get("stage", "") or "").strip().lower()
        if phase == "stage_stalled" or stage_name == "stage_stalled":
            return False
        stage = resolve_first_boot_stage(progress)
        if stage not in _BIRTH_ACTIVE_STAGES:
            return False
        if not birth_training_is_live(self.workspace_root, thread_running=self.is_running()):
            return False
        lock_active = birth_runner_lock_active(self.workspace_root)
        age = self._progress_timestamp_age_sec(progress)
        if age is None:
            return lock_active
        max_age = resolve_progress_active_max_age_sec(stage, runner_lock_active=lock_active)
        return age <= max_age

    def _write_runner_lock(self) -> None:
        payload = {
            "pid": int(os.getpid()),
            "host": socket.gethostname(),
            "runner": "thread",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "workspace_root": str(self.workspace_root),
        }
        try:
            self.runner_lock_path.parent.mkdir(parents=True, exist_ok=True)
            self.runner_lock_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("birth.runner_lock.write_failed path=%s", self.runner_lock_path, exc_info=True)

    def _read_runner_lock(self) -> Dict[str, Any] | None:
        return read_birth_runner_lock(self.workspace_root)

    def _clear_stale_runner_lock(self) -> None:
        if not self.runner_lock_path.exists():
            return
        if birth_runner_lock_active(self.workspace_root):
            return
        self._clear_runner_lock()

    def _clear_runner_lock(self) -> None:
        try:
            if self.runner_lock_path.exists():
                self.runner_lock_path.unlink()
        except OSError:
            logger.warning("birth.runner_lock.clear_failed path=%s", self.runner_lock_path, exc_info=True)


def configure_birth_workspace(workspace_root: Path | str | None = None) -> Path:
    """Configure the process-wide BirthService singleton workspace and reconcile orphan state."""
    return birth_service.configure_workspace(workspace_root)


# Singleton instance (workspace configured at app/launcher startup)
birth_service: BirthService = BirthService()
