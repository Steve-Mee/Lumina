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
    accept_champion_birth,
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


from lumina_launcher.services.birth_service_recovery import BirthServiceRecoveryMixin

class BirthService(BirthServiceRecoveryMixin):
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


    def _autonomous_recovery_enabled(self) -> bool:
        from lumina_core.birth.config import load_birth_v2_config

        cfg = load_birth_v2_config(self.workspace_root)
        return bool(cfg.curriculum.autonomous_recovery_enabled)







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

    def stop_birth(self, join_timeout: float = 0.15) -> Dict[str, Any]:
        """Signal stop + pause SSOT; default join is tiny so UI is never blocked.

        Wipe/teardown paths may pass a longer join_timeout. Training thread drains
        in the background — do not wait for full PPO teardown on the API path.
        """
        return stop_birth(self, join_timeout=join_timeout)

    def checkpoint_resumable(self) -> bool:
        # Hide resume only while actively training. During cooperative stop the
        # worker may still be alive while a valid on-disk checkpoint already exists —
        # show Resume immediately (do not wait for thread join).
        if self.is_running() and not self.is_stopping():
            return False
        from lumina_core.birth.checkpoint import is_checkpoint_resumable

        return is_checkpoint_resumable(self.workspace_root)


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

    def accept_champion_birth(
        self,
        target_trades: int | None = None,
        *,
        start: bool = True,
        source: str = "app",
    ) -> Dict[str, Any]:
        return accept_champion_birth(
            self, target_trades=target_trades, start=start, source=source
        )

    def reuse_data_birth(self, target_trades: int | None = None) -> Dict[str, Any]:
        return reuse_data_birth(self, target_trades=target_trades)

    def reset_birth(self) -> None:
        for f in [self.completed_flag, self.checkpoint_file]:
            if f.exists():
                f.unlink()
        logger.warning("Birth Phase state reset (development only)")


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
