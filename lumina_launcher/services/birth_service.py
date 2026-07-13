"""
LUMINA BIRTH SERVICE
====================

Production-grade service om de LuminaBirthEngine te starten en te monitoren.
Thin facade — status mapping, enrichment, and runner lifecycle live in bounded modules.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES
from lumina_core.logging_utils import get_logger
from lumina_launcher.services import birth_status_enricher, birth_status_mapper
# birth_runner reexport collapsed; direct submodules below for radical simplicity
from .birth_runner_start import (
    load_saved_birth_settings,
    preflight_historical_data,
    start_birth,
    stop_birth,
)
from .birth_runner_recovery import (
    expand_and_retry_stalled_stage,
    is_stage_stalled_recovery_eligible,
    resume_birth,
    resume_stalled_stage,
    retry_birth,
    reuse_data_birth,
)
from .birth_runner_lock import (
    clear_orphan_runner_lock_for_wipe,
    clear_runner_lock,
    clear_stale_runner_lock,
    mark_user_stopped_progress,
    read_runner_lock,
    reconcile_orphaned_birth_progress,
    reset_in_memory_birth_state,
    write_runner_lock,
)
from .birth_runner_wipe import (
    ensure_birth_stopped_for_wipe,
    wipe_all_birth_data,
    wipe_birth_training_artifacts,
)
from lumina_launcher.services.birth_status_mapper import resolve_terminal_birth_status
from lumina_launcher.core.workspace_root import resolve_birth_workspace_root  # direct (services reexport deleted)

logger = get_logger(__name__)

# Back-compat re-export for tests and launcher callers.
__all__ = [
    "BIRTH_ACTIVE_STAGES",
    "BirthService",
    "birth_service",
    "configure_birth_workspace",
    "resolve_birth_workspace_root",
    "resolve_terminal_birth_status",
]
_POLICY_REL = Path("lumina_agents") / "ppo" / "lumina_ppo_policy.zip"

# Re-export for callers that import from birth_service.
BIRTH_ACTIVE_STAGES = birth_status_mapper.BIRTH_ACTIVE_STAGES
_LIGHTWEIGHT_STATUS_PHASES = birth_status_mapper.LIGHTWEIGHT_STATUS_PHASES


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
        self._adaptive_intelligence_manager = None
        self._launcher_setup_cache: dict[str, Any] | None = None
        self._launcher_setup_cached_at: float = 0.0

        self.configure_workspace(resolve_birth_workspace_root())

        self._initialized = True
        logger.info("BirthService initialized (singleton) workspace=%s", self.workspace_root)

    def _get_adaptive_intelligence_manager(self):
        return birth_status_enricher.get_adaptive_intelligence_manager(self)

    def _should_use_lightweight_status_enrichment(self, progress: Dict[str, Any]) -> bool:
        return birth_status_mapper.should_use_lightweight_status_enrichment(self, progress)

    def _launcher_setup_status(self, *, lightweight: bool = False) -> dict[str, Any]:
        return birth_status_enricher.launcher_setup_status(self, lightweight=lightweight)

    def _enrich_birth_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return birth_status_enricher.enrich_birth_status(self, payload)

    def _resume_plateau_risk_fields(self) -> Dict[str, Any]:
        return birth_status_enricher.resume_plateau_risk_fields(self)

    def _adaptive_intelligence_status(self, *, lightweight: bool = False) -> Dict[str, Any]:
        return birth_status_enricher.adaptive_intelligence_status(self, lightweight=lightweight)

    def configure_workspace(self, workspace_root: Path | str | None = None) -> Path:
        """Bind state paths to repo root (safe when backend cwd != repo root)."""
        resolved = resolve_birth_workspace_root(workspace_root)
        if getattr(self, "workspace_root", None) != resolved:
            self._stalled_auto_resume_attempted = False
            self._adaptive_intelligence_manager = None
            self._launcher_setup_cache = None
            self._launcher_setup_cached_at = 0.0
        self.workspace_root = resolved
        self.progress_file = self.workspace_root / "state" / "lumina_birth_progress.json"
        self.legacy_progress_file = self.workspace_root / "state" / "first_boot_progress.json"
        self.completed_flag = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.checkpoint_file = self.workspace_root / "state" / "lumina_birth_checkpoint.json"
        self.runner_lock_path = self.workspace_root / "state" / "birth_runner.json"
        self.policy_path = self.workspace_root / _POLICY_REL
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        self.reconcile_orphaned_birth_progress()
        self._maybe_execute_autonomous_recovery()
        self._maybe_auto_resume_stalled_birth()
        return self.workspace_root

    def _autonomous_recovery_enabled(self) -> bool:
        from lumina_core.birth.config import load_birth_v2_config

        cfg = load_birth_v2_config(self.workspace_root)
        return bool(cfg.curriculum.autonomous_recovery_enabled)

    def _should_auto_resume_stalled_birth(self, progress: Dict[str, Any]) -> bool:
        if progress.get("user_initiated_stop") is True:
            return False
        if progress.get("retryable") is False:
            return False
        autonomous = self._autonomous_recovery_enabled()
        phase = str(progress.get("phase", "") or "").strip().lower()
        if phase in {"plateau_evolution", "stall_remediation", "curriculum_learning", "phoenix_cycle"}:
            return self._is_stage_stalled_recovery_eligible()
        if progress.get("needs_attention") is True and not autonomous:
            return False
        terminal = str(progress.get("terminal_stall_reason") or "").strip().lower()
        if terminal in {"plateau_evolution_exhausted", "stall_remediation_exhausted"}:
            return autonomous and progress.get("retryable") is not False
        if terminal == "phoenix_cycle" and autonomous:
            return True
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

    def execute_autonomous_recovery(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Execute recommended_recovery_action without operator input (Organism Autonomy Engine)."""
        if not self._autonomous_recovery_enabled():
            return {"status": "rejected", "message": "Autonomous recovery disabled in config."}
        progress = self._load_progress()
        action = str(progress.get("recommended_recovery_action") or "resume_stalled_stage").strip()
        if progress.get("autonomous_recovery_pending") is not True and not self._is_stage_stalled_recovery_eligible():
            return {
                "status": "rejected",
                "message": "No autonomous recovery pending.",
            }
        if action in {"expand_and_retry", "expand_data", "widen_horizon"}:
            return self.expand_and_retry_stalled_stage(target_trades=target_trades)
        if action == "phoenix_recovery":
            return self.phoenix_recovery_stalled_stage(target_trades=target_trades)
        return self.resume_stalled_stage(target_trades=target_trades)

    def _maybe_execute_autonomous_recovery(self) -> None:
        """Dispatch pending autonomous recovery before generic auto-resume."""
        if self.is_running():
            return
        progress = self._load_progress()
        if not self._autonomous_recovery_enabled():
            return
        if progress.get("retryable") is False:
            return
        phase = str(progress.get("phase", "") or "").strip().lower()
        if phase in {"certificate_failed", "certificate_remediation"}:
            logger.info("birth.autonomous_recovery certificate_retry")
            self.retry_birth()
            return
        if progress.get("autonomous_recovery_pending") is not True:
            return
        logger.info(
            "birth.autonomous_recovery dispatch action=%s",
            progress.get("recommended_recovery_action"),
        )
        self.execute_autonomous_recovery()

    def phoenix_recovery_stalled_stage(self, target_trades: int | None = None) -> Dict[str, Any]:
        """Phoenix-cycle resume: expand data + preserve checkpoint artifacts."""
        from lumina_core.birth.checkpoint import (
            read_checkpoint_payload,
            reset_adaptation_budget_for_manual_resume,
            write_checkpoint_payload,
        )

        if not self._is_stage_stalled_recovery_eligible():
            return {
                "status": "rejected",
                "message": "Phoenix recovery requires stage_stalled progress or checkpoint.",
            }
        reset_adaptation_budget_for_manual_resume(self.workspace_root)
        payload = read_checkpoint_payload(self.workspace_root)
        if payload:
            metrics = dict(payload.get("stage_metrics") or {})
            metrics["phoenix_cycle"] = True
            metrics["pending_data_expand"] = True
            payload["stage_metrics"] = metrics
            payload["phase"] = "phoenix_cycle"
            payload["terminal_stall_reason"] = "phoenix_cycle"
            write_checkpoint_payload(self.workspace_root, payload)
        return self.start_birth(
            target_trades=target_trades,
            force=False,
            explicit_user_start=True,
            continue_training=True,
            reuse_data=True,
            expand_data=True,
        )

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
        from lumina_core.birth.evolution_proof_gate import evolution_proof_passed

        thresholds = load_birth_v2_config(self.workspace_root).certificate_thresholds
        ok, _reason, _cert = validate_certificate_artifacts(
            self.workspace_root,
            thresholds=thresholds,
        )
        return ok and self.policy_path.is_file() and evolution_proof_passed(self.workspace_root)

    def certificate_ok(self) -> bool:
        from lumina_core.birth.birth_certificate import validate_certificate_artifacts
        from lumina_core.birth.config import load_birth_v2_config

        thresholds = load_birth_v2_config(self.workspace_root).certificate_thresholds
        ok, _reason, _cert = validate_certificate_artifacts(
            self.workspace_root,
            thresholds=thresholds,
        )
        return ok

    def evolution_proof_ok(self) -> bool:
        from lumina_core.birth.evolution_proof_gate import evolution_proof_passed

        return evolution_proof_passed(self.workspace_root)

    def real_trading_eligible(self) -> bool:
        from lumina_core.maturity.maturation_progress import maturation_eligible_for_real

        ok, _blockers = maturation_eligible_for_real(self.workspace_root)
        return ok

    def real_trading_blockers(self) -> list[str]:
        from lumina_core.maturity.maturation_progress import maturation_eligible_for_real

        _ok, blockers = maturation_eligible_for_real(self.workspace_root)
        return blockers

    def _load_saved_birth_settings(self) -> dict[str, Any]:
        return load_saved_birth_settings(self)

    def _preflight_historical_data(self, max_real_days: int) -> tuple[bool, str]:
        return preflight_historical_data(self, max_real_days)

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
        return start_birth(
            self,
            target_trades=target_trades,
            force=force,
            practice_mode=practice_mode,
            explicit_user_start=explicit_user_start,
            continue_training=continue_training,
            reuse_data=reuse_data,
            expand_data=expand_data,
        )

    def _sanitize_running_progress(self, progress: Dict[str, Any]) -> Dict[str, Any]:
        return birth_status_mapper.sanitize_running_progress(progress)

    def _resolve_elapsed_seconds_from_progress(self, progress: Dict[str, Any]) -> float:
        return birth_status_mapper.resolve_elapsed_seconds_from_progress(progress)

    def _is_stage_stalled_recovery_eligible(self) -> bool:
        return is_stage_stalled_recovery_eligible(self)

    def get_status(self) -> Dict[str, Any]:
        return birth_status_mapper.get_birth_status(self)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_stopping(self) -> bool:
        return self._stop_requested.is_set()

    def stop_birth(self, join_timeout: float = 15.0) -> Dict[str, Any]:
        return stop_birth(self, join_timeout=join_timeout)

    def checkpoint_resumable(self) -> bool:
        if self.is_running():
            return False
        from lumina_core.birth.checkpoint import is_checkpoint_resumable

        return is_checkpoint_resumable(self.workspace_root)

    def wipe_all_birth_data(
        self,
        *,
        join_timeout: float = 30.0,
        preserve_tick_cache: bool = False,
    ) -> Dict[str, Any]:
        return wipe_all_birth_data(
            self,
            join_timeout=join_timeout,
            preserve_tick_cache=preserve_tick_cache,
        )

    def wipe_birth_keep_tick_cache(self, *, join_timeout: float = 30.0) -> Dict[str, Any]:
        return self.wipe_all_birth_data(join_timeout=join_timeout, preserve_tick_cache=True)

    def _progress_is_persisted(self) -> bool:
        return self.progress_file.exists() or self.legacy_progress_file.exists()

    def _reset_in_memory_birth_state(self) -> None:
        reset_in_memory_birth_state(self)

    def _clear_orphan_runner_lock_for_wipe(self) -> None:
        clear_orphan_runner_lock_for_wipe(self)

    def _ensure_birth_stopped_for_wipe(self, *, join_timeout: float) -> Dict[str, Any] | None:
        return ensure_birth_stopped_for_wipe(self, join_timeout=join_timeout)

    def _wipe_birth_training_artifacts(self, *, join_timeout: float = 30.0) -> Dict[str, Any] | None:
        return wipe_birth_training_artifacts(self, join_timeout=join_timeout)

    def is_completed(self) -> bool:
        if not self.completed_flag.exists():
            return False
        return self.certificate_ok()

    def retry_birth(self, target_trades: int | None = None, *, wipe: bool = False) -> Dict[str, Any]:
        return retry_birth(self, target_trades=target_trades, wipe=wipe)

    def resume_stalled_stage(self, target_trades: int | None = None) -> Dict[str, Any]:
        return resume_stalled_stage(self, target_trades=target_trades)

    def expand_and_retry_stalled_stage(self, target_trades: int | None = None) -> Dict[str, Any]:
        return expand_and_retry_stalled_stage(self, target_trades=target_trades)

    def resume_birth(self, target_trades: int | None = None) -> Dict[str, Any]:
        return resume_birth(self, target_trades=target_trades)

    def reuse_data_birth(self, target_trades: int | None = None) -> Dict[str, Any]:
        return reuse_data_birth(self, target_trades=target_trades)

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
        return birth_status_mapper.progress_timestamp_age_sec(progress)

    def _mark_user_stopped_progress(self) -> None:
        mark_user_stopped_progress(self)

    def reconcile_orphaned_birth_progress(self) -> bool:
        return reconcile_orphaned_birth_progress(self)

    def _progress_indicates_running(self, progress: Dict[str, Any]) -> bool:
        return birth_status_mapper.progress_indicates_running(self, progress)

    def _write_runner_lock(self) -> None:
        write_runner_lock(self)

    def _read_runner_lock(self) -> Dict[str, Any] | None:
        return read_runner_lock(self)

    def _clear_stale_runner_lock(self) -> None:
        clear_stale_runner_lock(self)

    def _clear_runner_lock(self) -> None:
        clear_runner_lock(self)


def configure_birth_workspace(workspace_root: Path | str | None = None) -> Path:
    """Configure the process-wide BirthService singleton workspace and reconcile orphan state."""
    return birth_service.configure_workspace(workspace_root)


# Singleton instance (workspace configured at app/launcher startup)
birth_service: BirthService = BirthService()