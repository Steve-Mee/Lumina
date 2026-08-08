"""Birth runner preflight/stop helpers (M5)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from lumina_core.container import ApplicationContainer
from lumina_core.engine.runtime_entrypoint import _bind_headless_runtime_app
from lumina_core.order_gatekeeper import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_launcher.services.birth_runner_lock import mark_user_stopped_progress
from lumina_launcher.services.birth_status_mapper import BIRTH_ACTIVE_STAGES

logger = logging.getLogger(__name__)

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

def stop_birth(svc: Any, join_timeout: float = 0.15) -> Dict[str, Any]:
    """Cooperative stop: signal engine, persist pause SSOT, optional micro-join.

    Mark user-stop progress *before* any join so UI can return to Genesis immediately
    (checkpoint_resumable / paused stage) without waiting for PPO thread teardown.
    Default join is a micro-wait only; wipe paths may pass a longer timeout.
    join_timeout <= 0 skips join entirely (signal + SSOT only).
    """
    had_thread = svc.is_running()
    progress = svc._load_progress()
    stage = str(progress.get("stage", "") or "").strip().lower()
    progress_active = stage in BIRTH_ACTIVE_STAGES

    if not had_thread and not progress_active and not svc.is_stopping():
        return {
            "status": "not_running",
            "message": "No active Birth Phase.",
            "checkpoint_resumable": bool(svc.checkpoint_resumable()),
        }

    svc._stop_requested.set()
    svc.pause_flag_path.parent.mkdir(parents=True, exist_ok=True)
    svc.pause_flag_path.write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")

    # Persist pause SSOT first — UI + resume button must not wait on thread join.
    mark_user_stopped_progress(svc)

    still = bool(svc.is_running())
    if had_thread and svc._thread is not None and float(join_timeout) > 0:
        # Micro cooperative wait only; never block HTTP for full PPO drain.
        svc._thread.join(timeout=max(0.05, float(join_timeout)))
        still = bool(svc.is_running())

    if had_thread:
        return {
            "status": "stopping" if still else "stopped",
            "message": (
                "Birth Phase stop requested — engine is finalizing checkpoint."
                if still
                else "Birth Phase stopped."
            ),
            "checkpoint_resumable": bool(svc.checkpoint_resumable()),
            "thread_running": still,
        }

    return {
        "status": "stopped",
        "message": "Birth Phase stop recorded.",
        "checkpoint_resumable": bool(svc.checkpoint_resumable()),
        "thread_running": False,
    }
