#!/usr/bin/env python3
"""
LUMINA BIRTH SERVICE
====================

Production-grade service om de LuminaBirthEngine te starten en te monitoren.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from lumina_core.container import ApplicationContainer
from lumina_core.engine.runtime_entrypoint import _bind_headless_runtime_app
from lumina_core.lumina_birth_engine import LuminaBirthEngine
from lumina_core.first_boot_ui import FIRST_BOOT_DEFAULT_TRADES
from lumina_core.logging_utils import get_logger

logger = get_logger(__name__)

# lumina_launcher/services/birth_service.py -> repo root
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_REL = Path("lumina_agents") / "ppo" / "lumina_ppo_policy.zip"


def resolve_birth_workspace_root(explicit: Path | str | None = None) -> Path:
    """Resolve SSOT workspace root (never rely on process cwd)."""
    if explicit is not None and str(explicit).strip():
        return Path(explicit).expanduser().resolve()
    override = os.getenv("LUMINA_WORKSPACE_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_REPO_ROOT.resolve()


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

        self.configure_workspace(resolve_birth_workspace_root())

        self._initialized = True
        logger.info("BirthService initialized (singleton) workspace=%s", self.workspace_root)

    def configure_workspace(self, workspace_root: Path | str | None = None) -> Path:
        """Bind state paths to repo root (safe when backend cwd != repo root)."""
        self.workspace_root = resolve_birth_workspace_root(workspace_root)
        self.progress_file = self.workspace_root / "state" / "lumina_birth_progress.json"
        self.completed_flag = self.workspace_root / "state" / "lumina_birth_completed.flag"
        self.checkpoint_file = self.workspace_root / "state" / "lumina_birth_checkpoint.json"
        self.policy_path = self.workspace_root / _POLICY_REL
        self.pause_flag_path = self.workspace_root / "state" / "first_boot_pause_requested"
        return self.workspace_root

    @property
    def stop_event(self) -> threading.Event:
        return self._stop_requested

    def artifacts_ok(self) -> bool:
        return self.is_completed() and self.policy_path.is_file()

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
                return False, (
                    "Geen historische marktdata beschikbaar voor certified training. "
                    "Controleer Crosstrade credentials (CROSSTRADE_TOKEN), instrument en netwerk."
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
        target_trades: int = 25000,
        force: bool = False,
        practice_mode: bool = False,
        explicit_user_start: bool = False,
    ) -> Dict[str, Any]:
        if not explicit_user_start:
            return {
                "status": "rejected",
                "message": "Birth Phase start requires an explicit user action (Start Birth Phase).",
            }

        if self.is_running():
            return {"status": "already_running", "message": "Birth Phase is already in progress"}

        if self.is_completed() and not force and not practice_mode:
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
        resolved_target = int(saved_settings.get("training_trades", target_trades) or target_trades or FIRST_BOOT_DEFAULT_TRADES)
        resolved_max_real_days = int(saved_settings.get("max_real_days", 365) or 365)
        resolved_prefer_real_data_only = (
            False if practice_mode else bool(saved_settings.get("prefer_real_data_only", True))
        )

        if not practice_mode:
            preflight_ok, preflight_msg = self._preflight_historical_data(resolved_max_real_days)
            if not preflight_ok:
                return {
                    "status": "rejected",
                    "message": preflight_msg or "Historische data niet beschikbaar voor certified training.",
                }

        def _run_birth() -> None:
            try:
                logger.info(
                    "Starting Birth Phase with target_trades=%s max_real_days=%s prefer_real_data_only=%s practice_mode=%s workspace=%s",
                    resolved_target,
                    resolved_max_real_days,
                    resolved_prefer_real_data_only,
                    bool(practice_mode),
                    self.workspace_root,
                )
                previous_cfg = os.getenv("LUMINA_CONFIG", "")
                previous_cwd = Path.cwd()
                os.environ["LUMINA_CONFIG"] = str((self.workspace_root / "config.yaml").resolve())
                try:
                    os.chdir(self.workspace_root)
                    container = ApplicationContainer()
                    _bind_headless_runtime_app(container)
                    engine = LuminaBirthEngine(
                        runtime=container.engine,
                        market_data_service=container.market_data_service,
                        config={"first_boot": saved_settings},
                        workspace_root=self.workspace_root,
                        stop_event=self._stop_requested,
                    )
                    self._result = engine.run_birth_phase(
                        target_trades=resolved_target,
                        max_real_days=resolved_max_real_days,
                        prefer_real_data_only=resolved_prefer_real_data_only,
                        chunk_size=50000,
                        ppo_update_timesteps=25000,
                        force=force,
                        practice_mode=bool(practice_mode),
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

        self._thread = threading.Thread(target=_run_birth, daemon=True, name="LuminaBirthThread")
        self._thread.start()

        return {
            "status": "started",
            "target_trades": resolved_target,
            "max_real_days": resolved_max_real_days,
            "prefer_real_data_only": resolved_prefer_real_data_only,
            "practice_mode": bool(practice_mode),
            "message": (
                "Practice Birth Phase started in background"
                if practice_mode
                else "Birth Phase started in background"
            ),
        }

    def get_status(self) -> Dict[str, Any]:
        if self.completed_flag.exists():
            return {
                "status": "completed",
                "progress_pct": 100,
                "message": "Birth Phase voltooid",
                "result": self._result,
            }

        if self._error:
            return {"status": "error", "error": self._error, "message": "Birth Phase gefaald"}

        if self.is_running():
            progress = self._load_progress()
            return {
                "status": "running",
                "progress": progress,
                "elapsed_seconds": round(time.time() - self._start_time, 1) if self._start_time else 0,
                "message": "Birth Phase draait...",
            }

        if isinstance(self._result, dict) and self._result:
            progress = self._load_progress()
            status = str(self._result.get("status", "idle") or "idle")
            msg = str(progress.get("message") or self._result.get("message") or "Birth Phase klaar.")
            return {"status": status, "progress": progress, "result": self._result, "message": msg}

        return {"status": "idle", "progress": self._load_progress(), "message": "Birth Phase nog niet gestart"}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_stopping(self) -> bool:
        return self._stop_requested.is_set()

    def stop_birth(self, join_timeout: float = 5.0) -> Dict[str, Any]:
        """Cooperative stop: signal engine via event + pause flag, optionally join thread."""
        had_thread = self.is_running()
        progress = self._load_progress()
        stage = str(progress.get("stage", "") or "").strip().lower()
        running_stages = {
            "detected",
            "loading_data",
            "training_running",
            "pipeline_boot",
            "historical_loaded",
            "synthetic_top_up",
            "parallel_simulation",
            "ppo_training",
            "deferred_calendar",
        }
        progress_active = stage in running_stages

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
            return {"status": "stopped", "message": "Birth Phase gestopt."}

        if progress_active:
            return {
                "status": "stopping",
                "message": "Stop-aanvraag vastgelegd (geen actieve thread in dit proces).",
            }

        return {"status": "stopping", "message": "Birth Phase stop aangevraagd."}

    def is_completed(self) -> bool:
        return self.completed_flag.exists()

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
        return {"trades_done": 0, "target_trades": 25000, "progress_pct": 0, "ppo_steps": 0, "stage": "not_started"}


def configure_birth_workspace(workspace_root: Path | str | None = None) -> Path:
    """Configure the process-wide BirthService singleton workspace."""
    return birth_service.configure_workspace(workspace_root)


# Singleton instance (workspace configured at app/launcher startup)
birth_service: BirthService = BirthService()
