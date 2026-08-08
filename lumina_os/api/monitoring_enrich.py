"""React dashboard observability enrich (M5)."""
from __future__ import annotations

from pathlib import Path
import os
from datetime import datetime, timezone
from typing import Any

from lumina_core.first_boot_progress import (
    resolve_effective_first_boot_target_trades,
    resolve_first_boot_completed_trades,
    resolve_first_boot_stage,
    resolve_first_boot_target_trades,
    resolve_ppo_training_progress,
)
from lumina_core.runtime_session import resolve_runtime_session_state


def _mon():
    from lumina_os.api import monitoring as mon
    return mon

def enrich_observability_snapshot_for_react_dashboard(
    snapshot: dict[str, Any],
    *,
    state_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Return a **shallow-copy** observability snapshot with ``_lumina_ui`` injected.

    The React hook prefers ``_lumina_ui`` embedded keys over raw Prometheus scraping.
    """
    # BIRTH ENGINE 2026-05-17
    sd = _mon().resolve_state_directory() if state_dir is None else Path(state_dir)
    config_payload = _mon()._safe_read_yaml(sd.parent / "config.yaml")
    boot = _mon()._safe_read_json(sd / "lumina_birth_progress.json")
    if not boot:
        boot = _mon()._safe_read_json(sd / "first_boot_progress.json")
    ppo_meta = _mon()._safe_read_json(sd / "ppo_policy_metadata.json")
    twin_tail = _mon()._last_json_object_from_jsonl(sd / "monitoring_twin_training.jsonl")

    # --- Prometheus-preferring values ---
    trades_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_TRADE_NAMES)
    ppo_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_PPO_STEP_NAMES)
    twin_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_APPROVAL_NAMES)
    cpu_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_CPU)
    gpu_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_GPU)
    ram_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_RAM)
    vel_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_VELOCITY)
    synth_prom = _mon()._first_metric_positive(snapshot, _mon()._PROM_SYNTH)
    eta_prom = _mon()._coerce_eta_minutes(snapshot)

    phase_obs = _mon()._phase_from_snapshot(snapshot)

    # --- File-derived fallbacks (training / launcher state) ---
    trades_fb = float(resolve_first_boot_completed_trades(boot))
    target_fb_cfg = float(resolve_first_boot_target_trades(config_payload))
    target_fb_progress = float(resolve_effective_first_boot_target_trades(progress=boot, config_payload=config_payload))
    stage_fb_normalized = resolve_first_boot_stage(boot)
    current_mode = str(
        os.environ.get("LUMINA_MODE")
        or os.environ.get("TRADE_MODE")
        or config_payload.get("mode", "sim")
    ).strip().lower()
    user_configured = (sd / "first_boot_user_configured.flag").exists()
    runtime_session = resolve_runtime_session_state(
        first_boot_stage=stage_fb_normalized,
        process_alive=_mon()._runtime_alive_from_state(sd),
        current_mode=current_mode,
        first_boot_timestamp=str(boot.get("timestamp") or ""),
    )
    target_effective = target_fb_progress if target_fb_progress > 0 else target_fb_cfg
    ppo_steps_fb, ppo_total_fb, ppo_progress_fb = resolve_ppo_training_progress(boot)

    birth_certificate_ok = False
    birth_oos_sharpe = 0.0
    try:
        from lumina_core.birth.birth_certificate import validate_certificate_artifacts
        from lumina_core.birth.config import load_birth_v2_config

        cert_ok, _, cert = validate_certificate_artifacts(
            sd.parent,
            thresholds=load_birth_v2_config(sd.parent).certificate_thresholds,
        )
        birth_certificate_ok = bool(cert_ok)
        if cert is not None:
            birth_oos_sharpe = float(cert.oos_sharpe)
    except Exception:
        pass

    try:
        ppo_fb = float(
            boot.get("ppo_steps")
            or boot.get("policy_steps")
            or ppo_meta.get("total_training_steps")
            or 0
        )
    except (TypeError, ValueError):
        ppo_fb = 0.0
    ppo_steps_effective = int(round(ppo_prom)) if ppo_prom is not None else int(round(max(0.0, ppo_fb)))
    ppo_total_effective = int(max(1, ppo_total_fb))
    ppo_progress_effective = (
        max(0.0, min(100.0, (float(ppo_steps_effective) / float(max(1, ppo_total_effective))) * 100.0))
        if ppo_progress_fb is None
        else max(0.0, min(100.0, float(ppo_progress_fb)))
    )

    twin_fb: float
    try:
        if boot.get("approval_twin_reward") is not None:
            twin_fb = float(boot["approval_twin_reward"])
        elif twin_tail.get("reward") is not None:
            twin_fb = float(twin_tail["reward"])
        else:
            twin_fb = float("nan")
    except (TypeError, ValueError):
        twin_fb = float("nan")

    phase_fb = str(boot.get("phase") or boot.get("stage") or "").strip()

    hist_fb = boot.get("actual_real_days_loaded")
    if hist_fb is None:
        hist_fb = boot.get("estimated_real_days")
    try:
        historical_days_fb = int(hist_fb) if hist_fb is not None else 0
    except (TypeError, ValueError):
        historical_days_fb = 0

    try:
        synthetic_fb = float(boot["synthetic_blend_pct"])
    except (KeyError, TypeError, ValueError):
        synthetic_fb = float("nan")

    # ETA from progress heuristics (very rough — prefer Prometheus / explicit keys)
    eta_fb: float | None = None
    try:
        raw_eta = boot.get("eta_minutes")
        if raw_eta is not None:
            eta_fb = float(raw_eta)
    except (TypeError, ValueError):
        eta_fb = None

    runtime_alive = _mon()._runtime_alive_from_state(sd)
    ppo_progress_stale = False
    if stage_fb_normalized == "training_running" and str(boot.get("phase") or "").strip().lower() == "ppo_training":
        parsed_ts = None
        raw_ts = str(boot.get("timestamp") or "").strip()
        if raw_ts:
            try:
                parsed_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if parsed_ts.tzinfo is None:
                    parsed_ts = parsed_ts.replace(tzinfo=timezone.utc)
                parsed_ts = parsed_ts.astimezone(timezone.utc)
            except Exception:
                parsed_ts = None
        if parsed_ts is not None:
            age = (datetime.now(timezone.utc) - parsed_ts).total_seconds()
            ppo_progress_stale = runtime_alive and age > 120

    ui: dict[str, Any] = {
        "trades_completed": (
            int(round(trades_prom)) if trades_prom is not None else int(round(max(0.0, trades_fb)))
        ),
        "training_completed_trades": (
            int(round(trades_prom)) if trades_prom is not None else int(round(max(0.0, trades_fb)))
        ),
        "training_target_trades": (
            int(round(max(1.0, target_effective)))
            if runtime_session.training_target_applicable and user_configured
            else 0
        ),
        "first_boot_stage": stage_fb_normalized,
        "ppo_steps": ppo_steps_effective,
        "ppo_timesteps_total": ppo_total_effective,
        "ppo_progress_pct": round(ppo_progress_effective, 2),
        "approval_twin_reward": float(twin_prom)
        if twin_prom is not None
        else (float(twin_fb) if twin_fb == twin_fb else 0.0),
        "cpu": _mon()._clamp_pct(cpu_prom) if cpu_prom is not None else 0.0,
        "gpu": _mon()._clamp_pct(gpu_prom) if gpu_prom is not None else 0.0,
        "ram": _mon()._clamp_pct(ram_prom) if ram_prom is not None else 0.0,
        "velocity": float(vel_prom) if vel_prom is not None else 0.0,
        "phase": phase_obs or phase_fb,
        "historical_days": historical_days_fb,
        "synthetic_percent": float(synth_prom)
        if synth_prom is not None
        else (float(synthetic_fb) if synthetic_fb == synthetic_fb else 0.0),
        "eta_minutes": float(eta_prom) if eta_prom is not None else eta_fb,
        "session_kind": runtime_session.session_kind,
        "session_active": runtime_session.session_active,
        "training_target_applicable": runtime_session.training_target_applicable and user_configured,
        "last_activity_ts": runtime_session.last_activity_ts,
        "activity_stale": runtime_session.activity_stale or ppo_progress_stale,
        "birth_certificate_ok": birth_certificate_ok,
        "birth_oos_sharpe": round(birth_oos_sharpe, 4),
    }

    missing = set(_mon().LUMINA_UI_FIELDS) - set(ui.keys())
    if missing:
        raise RuntimeError(f"Internal invariant: Lumina UI fields incomplete: {sorted(missing)}")

    enriched = dict(snapshot)
    enriched["_lumina_ui"] = ui

    return enriched
