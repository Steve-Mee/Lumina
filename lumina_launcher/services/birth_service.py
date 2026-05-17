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
from pathlib import Path
from typing import Any, Dict, Optional

from lumina_core.lumina_birth_engine import LuminaBirthEngine
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
        return self.workspace_root

    def artifacts_ok(self) -> bool:
        return self.is_completed() and self.policy_path.is_file()

    def start_birth(self, target_trades: int = 25000, force: bool = False) -> Dict[str, Any]:
        if self.is_running():
            return {"status": "already_running", "message": "Birth Phase is already in progress"}

        if self.is_completed() and not force:
            return {"status": "already_completed", "message": "Birth Phase already completed"}

        self._result = None
        self._error = None
        self._start_time = time.time()

        def _run_birth() -> None:
            try:
                logger.info(
                    "Starting Birth Phase with target_trades=%s workspace=%s",
                    target_trades,
                    self.workspace_root,
                )
                engine = LuminaBirthEngine(workspace_root=self.workspace_root)
                self._result = engine.run_birth_phase(
                    target_trades=target_trades,
                    max_real_days=365,
                    prefer_real_data_only=True,
                    chunk_size=50000,
                    ppo_update_timesteps=25000,
                    force=force,
                )
                logger.info("Birth Phase completed successfully")
            except Exception as e:
                self._error = str(e)
                logger.exception("Birth Phase failed: %s", e)

        self._thread = threading.Thread(target=_run_birth, daemon=True, name="LuminaBirthThread")
        self._thread.start()

        return {"status": "started", "target_trades": target_trades, "message": "Birth Phase started in background"}

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

        return {"status": "idle", "progress": self._load_progress(), "message": "Birth Phase nog niet gestart"}

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

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
