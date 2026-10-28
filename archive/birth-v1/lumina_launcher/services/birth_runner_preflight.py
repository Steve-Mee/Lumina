"""Birth runner preflight/stop helpers (M5)."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from lumina_core.container import ApplicationContainer
from lumina_core.engine.runtime_entrypoint import _bind_headless_runtime_app
from lumina_core.birth.foundation_history import foundation_history_start_days
from lumina_core.order_gatekeeper import is_stale_contract_symbol, roll_stale_contract_symbol
from lumina_launcher.services.birth_runner_lock import mark_user_stopped_progress
from lumina_launcher.services.birth_status_mapper import BIRTH_ACTIVE_STAGES

logger = logging.getLogger(__name__)

_FABRIC_PROVIDERS = frozenset({"ninjatrader", "nt", "fabric"})


def _invalidate_fabric_cert_after_history_fail(workspace: Path, *, reason: str) -> None:
    """Paper GREEN must not survive a live Fabric history failure."""
    try:
        from lumina_launcher.services.fabric_link_certificate import invalidate_certificate

        invalidate_certificate(workspace, reason=reason)
    except Exception:
        logger.debug("birth.preflight.invalidate_cert_failed reason=%s", reason, exc_info=True)


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


def _resolve_live_provider_from_yaml(workspace_root: Path) -> str:
    """SSOT from config.yaml / env — do not trust empty container attrs."""
    env = str(os.getenv("BROKER_LIVE_PROVIDER") or "").strip().lower()
    if env in _FABRIC_PROVIDERS or env == "crosstrade":
        return env
    config_path = workspace_root / "config.yaml"
    if config_path.is_file():
        try:
            cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            broker = cfg.get("broker") if isinstance(cfg, dict) else None
            if isinstance(broker, dict):
                lp = str(broker.get("live_provider") or "").strip().lower()
                if lp:
                    return lp
        except Exception:
            pass
    return ""


def _fabric_history_remediation(
    *,
    instrument: str,
    stale_msg: str,
    connect_refused: bool,
    auth_failed: bool = False,
) -> str:
    if auth_failed:
        return (
            "Fabric host draait, maar Brain-authenticatie faalt (token mismatch)."
            f"{stale_msg}"
            "Setup → Repair NinjaTrader connection (token sync), daarna NinjaTrader "
            "één keer herstarten zodat de AddOn User-env/fabric.json AuthToken herlaadt. "
            "LUMINA Link moet Brain sessions ≥ 1 tonen (niet AMBER met 0 sessions). "
            "Dit pad gebruikt alleen native NT Fabric (niet cloud market data)."
        )
    if connect_refused:
        return (
            "Geen verbinding met Execution Fabric (127.0.0.1:50051)."
            f"{stale_msg}"
            "Start NinjaTrader, wacht tot datafeed Connected is, open New → LUMINA (host running), "
            "controleer LUMINA_FABRIC_TOKEN, daarna in Lumina: Test connection (historical_bars GREEN) "
            "en Retry birth. Dit pad gebruikt alleen native NT Fabric (niet cloud market data)."
        )
    return (
        "Geen historische marktdata via Execution Fabric / NinjaTrader."
        f"{stale_msg}"
        "Controleer: NT8 AddOn actief (New → LUMINA), poort 127.0.0.1:50051, LUMINA_FABRIC_TOKEN, "
        "data provider Connected, instrument "
        f"{instrument or 'MES'}, "
        "en Run fabric diagnostic (historical_bars moet GREEN). "
        "Dit pad gebruikt alleen native NT Fabric (niet cloud market data)."
    )


def preflight_historical_data(svc: Any, max_real_days: int) -> tuple[bool, str]:
    """Probe historical market data before certified Birth Phase starts.

    Uses Fabric/NT when ``broker.live_provider=ninjatrader``; otherwise CrossTrade.
    """
    previous_cfg = os.getenv("LUMINA_CONFIG", "")
    previous_cwd = Path.cwd()
    workspace = Path(svc.workspace_root)
    os.environ["LUMINA_CONFIG"] = str((workspace / "config.yaml").resolve())
    yaml_provider = _resolve_live_provider_from_yaml(workspace)
    try:
        os.chdir(workspace)
        try:
            from lumina_core.engine.engine_config_helpers import clear_yaml_config_cache

            clear_yaml_config_cache()
        except Exception:
            pass
        container = ApplicationContainer()
        _bind_headless_runtime_app(container)
        # Force engine config to yaml SSOT when container was poisoned to crosstrade.
        cfg_obj = getattr(container, "config", None)
        if yaml_provider in _FABRIC_PROVIDERS and cfg_obj is not None:
            eng_lp = str(getattr(cfg_obj, "broker_live_provider", "") or "").strip().lower()
            if eng_lp not in _FABRIC_PROVIDERS:
                logger.warning(
                    "birth.preflight.provider_override engine=%s yaml=%s",
                    eng_lp,
                    yaml_provider,
                )
                try:
                    cfg_obj.broker_live_provider = yaml_provider
                except Exception:
                    pass
                eng = getattr(container, "engine", None)
                if eng is not None and getattr(eng, "config", None) is not None:
                    try:
                        eng.config.broker_live_provider = yaml_provider
                    except Exception:
                        pass
        mds = container.market_data_service
        if mds is None or not hasattr(mds, "load_historical_ohlc_extended"):
            return False, (
                "Certified Birth Phase vereist MarketDataService.load_historical_ohlc_extended; "
                "service niet beschikbaar."
            )
        cfg = getattr(container, "config", None)
        live_provider = str(getattr(cfg, "broker_live_provider", "") or "").strip().lower()
        # Prefer yaml/env when container is empty or disagree (stale process cache).
        if yaml_provider in _FABRIC_PROVIDERS:
            live_provider = yaml_provider
        elif not live_provider and yaml_provider:
            live_provider = yaml_provider

        instrument = str(getattr(cfg, "instrument", "") or "MES").strip()
        stale_msg = ""
        if instrument and is_stale_contract_symbol(instrument):
            rolled = roll_stale_contract_symbol(instrument)
            stale_msg = (
                f" Instrument {instrument} is verlopen; probeer {rolled} in config.yaml. "
                if rolled != instrument.upper()
                else f" Instrument {instrument} lijkt verlopen. "
            )

        # Always-on: token SSOT + supervisor + live auth before history load.
        if live_provider in _FABRIC_PROVIDERS:
            try:
                from lumina_launcher.services.fabric_link_ensure import (
                    ensure_fabric_token_aligned_and_live,
                )

                ensured = ensure_fabric_token_aligned_and_live(
                    engine_config=cfg,
                    workspace_root=workspace,
                    mode_context="sim",
                    connect_timeout_seconds=8.0,
                    start_supervisor=True,
                )
                if not ensured.get("ok"):
                    code = str(ensured.get("code") or "ERROR")
                    _invalidate_fabric_cert_after_history_fail(
                        workspace, reason=f"history_preflight_{code.lower()}"
                    )
                    return False, str(
                        ensured.get("message")
                        or "Fabric link not live — Repair connection / restart NT once."
                    )
            except Exception as sup_exc:
                logger.warning("birth.preflight.supervisor_probe_failed: %s", sup_exc, exc_info=True)

        def _load_once() -> tuple[Any, Exception | None]:
            try:
                rows = mds.load_historical_ohlc_extended(
                    days_back=max(1, min(int(max_real_days), foundation_history_start_days())),
                    limit=500,
                    ticks_per_bar=4,
                )
                return rows, None
            except Exception as exc:
                return None, exc

        rows, load_exc = _load_once()
        # One short retry when Fabric path and host may still be binding after NT start.
        if (not rows) and live_provider in _FABRIC_PROVIDERS:
            time.sleep(4.0)
            rows2, load_exc2 = _load_once()
            if rows2:
                rows, load_exc = rows2, None
            elif load_exc2 is not None:
                load_exc = load_exc2

        if load_exc is not None:
            logger.warning("Birth preflight historical data failed: %s", load_exc, exc_info=True)
            err = str(load_exc)
            err_l = err.lower()
            connect_refused = any(
                x in err_l
                for x in ("connection refused", "unavailable", "failed to connect", "10061", "statuscode.unavailable")
            )
            auth_failed = any(
                x in err_l for x in ("auth", "token mismatch", "invalid fabric token", "invalid token")
            )
            _invalidate_fabric_cert_after_history_fail(workspace, reason="history_preflight_exception")
            if live_provider in _FABRIC_PROVIDERS or connect_refused or auth_failed:
                return False, _fabric_history_remediation(
                    instrument=instrument,
                    stale_msg=stale_msg,
                    connect_refused=connect_refused and not auth_failed,
                    auth_failed=auth_failed,
                )
            return False, f"Historische data preflight mislukt: {load_exc}"

        if not rows:
            _invalidate_fabric_cert_after_history_fail(workspace, reason="history_preflight_empty")
            if live_provider in _FABRIC_PROVIDERS:
                # Re-probe so empty history after host-up surfaces AUTH vs NO_BARS.
                try:
                    from lumina_core.broker.ninjatrader.fabric_auth_probe import (
                        probe_fabric_auth,
                        remediation_for_probe,
                    )

                    probe = probe_fabric_auth(config=cfg, mode_context="sim")
                    if not probe.ok:
                        return False, remediation_for_probe(probe)
                except Exception:
                    pass
                return False, _fabric_history_remediation(
                    instrument=instrument,
                    stale_msg=stale_msg,
                    connect_refused=False,
                    auth_failed=False,
                )
            # Fail-closed: never demand CrossTrade when product path is Fabric/NT.
            # (yaml may be empty here only when provider resolution missed — still no CT hop.)
            return False, (
                "Geen historische marktdata beschikbaar voor certified training."
                f"{stale_msg}"
                "Controleer Execution Fabric / NinjaTrader: New → LUMINA (host running), "
                "127.0.0.1:50051, LUMINA_FABRIC_TOKEN, datafeed Connected, daarna Test connection "
                "(historical_bars GREEN). Dit pad gebruikt native NT Fabric — geen CrossTrade."
            )
        return True, ""
    except Exception as exc:
        logger.warning("Birth preflight historical data failed: %s", exc, exc_info=True)
        _invalidate_fabric_cert_after_history_fail(workspace, reason="history_preflight_outer")
        if yaml_provider in _FABRIC_PROVIDERS:
            err_l = str(exc).lower()
            auth_failed = "auth" in err_l or "token" in err_l
            return False, _fabric_history_remediation(
                instrument="",
                stale_msg="",
                connect_refused=(
                    not auth_failed
                    and ("refused" in err_l or "unavailable" in err_l)
                ),
                auth_failed=auth_failed,
            )
        return False, f"Historische data preflight mislukt: {exc}"
    finally:
        os.chdir(previous_cwd)
        if previous_cfg:
            os.environ["LUMINA_CONFIG"] = previous_cfg
        else:
            os.environ.pop("LUMINA_CONFIG", None)


def demote_stale_history_failure_progress(svc: Any) -> bool:
    """If birth is not running and progress is a *stale* history error, demote for UI honesty.

    Fresh failures (last 15 minutes) keep their live message (AUTH_FAILED etc.) —
    never overwrite with generic "Vorige birth-run" theater.

    Returns True if progress was rewritten.
    """
    if svc.is_running():
        return False
    try:
        progress = svc._load_progress()
    except Exception:
        return False
    if not isinstance(progress, dict):
        return False
    stage = str(progress.get("stage") or "").strip().lower()
    phase = str(progress.get("phase") or "").strip().lower()
    code = str(progress.get("attention_reason_code") or "").strip().lower()
    if stage != "error" or phase != "loading_history_failed":
        if code != "history_unavailable":
            return False

    msg = str(progress.get("message") or progress.get("last_error") or "")
    msg_l = msg.lower()
    # Keep live AUTH / token diagnostics intact.
    if any(
        x in msg_l
        for x in (
            "token mismatch",
            "auth",
            "authenticatie",
            "brain-auth",
            "brain sessions",
            "repair",
        )
    ):
        return False

    # Fresh failures: do not demote (operator is mid-retry).
    try:
        ts = str(progress.get("timestamp") or progress.get("residual_failure_at") or "")
        if ts:
            # ISO timestamps from write_birth_progress
            from datetime import datetime as _dt

            parsed = _dt.fromisoformat(ts.replace("Z", "+00:00"))
            age_sec = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
            if age_sec < 15 * 60:
                return False
    except Exception:
        pass

    # Residual failure — keep checkpoint but rewrite message for ninjatrader workspaces.
    yaml_provider = _resolve_live_provider_from_yaml(Path(svc.workspace_root))
    if yaml_provider in _FABRIC_PROVIDERS or "CROSSTRADE" in msg.upper():
        new_msg = (
            "Vorige birth-run stopte: geen historische data op dat moment (Execution Fabric / NinjaTrader). "
            "Zorg dat NT open is, New → LUMINA host running, Test connection GREEN, daarna Retry birth. "
            "Bij token mismatch: Repair connection + herstart NT één keer (Brain sessions ≥ 1). "
            "Dit pad gebruikt alleen native NT Fabric (niet cloud market data)."
        )
        progress["message"] = new_msg
        progress["last_error"] = new_msg
        progress["attention_reason_code"] = "history_unavailable_residual"
        progress["needs_attention"] = True
        # Keep stage=error so operator sees recovery, but mark residual for UI.
        progress["residual_failure"] = True
        progress["residual_failure_at"] = datetime.now(timezone.utc).isoformat()
        try:
            path = Path(svc.progress_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            import json

            path.write_text(json.dumps(progress, indent=2, default=str), encoding="utf-8")
            return True
        except Exception:
            logger.debug("demote_stale_history_failure_progress save failed", exc_info=True)
    return False


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
