"""Monitoring ops/dashboard endpoints (global residual)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Header

from lumina_os.backend.monitoring_endpoints_helpers import _check_api_key
from lumina_os.monitoring.snapshots import (
    load_json_file as _load_json_file,
    load_jsonl_file as _load_jsonl_file,
    monitoring_paths as _monitoring_paths,
    repo_state_dir as _repo_state_dir,
)

async def get_ops_data(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    twin = _load_jsonl_file(state / "monitoring_twin_decisions.jsonl", limit=20)
    gate = _load_jsonl_file(state / "monitoring_gate_rejections.jsonl", limit=50)
    shadow: dict[str, Any] = {}
    shadow_path = state / "evolution_shadow_runs.json"
    if shadow_path.is_file():
        try:
            parsed = json.loads(shadow_path.read_text(encoding="utf-8"))
            shadow = parsed if isinstance(parsed, dict) else {}
        except (OSError, json.JSONDecodeError):
            shadow = {}
    daily_pnl = _load_jsonl_file(state / "monitoring_daily_pnl.jsonl", limit=30)
    # Perfect Birth Phase KPIs (twin accuracy vs Steve, autonomy, alignment)
    twin_accuracy = _load_jsonl_file(state / "monitoring_twin_training.jsonl", limit=5)
    autonomy_rollup = _load_jsonl_file(state / "monitoring_autonomy_metrics.jsonl", limit=5)
    shadow_align = _load_jsonl_file(state / "monitoring_shadow_twin_alignment.jsonl", limit=10)
    phase2_recent = _load_jsonl_file(state / "monitoring_phase2_autonomy.jsonl", limit=20)
    # First-class Twin observability rollup (agreement/calibration/mode progress)
    twin_observability: dict[str, Any] = {}
    try:
        from lumina_core.evolution.twin_training_service import TwinTrainingService

        m = TwinTrainingService().metrics(decision_window=100, series_limit=14)
        twin_observability = {
            "mode": m.get("mode"),
            "authority": m.get("authority"),
            "twin_steve_agreement_pct": m.get("twin_steve_agreement_pct"),
            "twin_agreement_pct": m.get("twin_agreement_pct"),
            "rolling_agreement": m.get("rolling_agreement"),
            "agreement_over_time": m.get("agreement_over_time"),
            "risk_flags_caught": m.get("risk_flags_caught"),
            "risk_flags_missed": m.get("risk_flags_missed"),
            "risk_flags_catch_rate_pct": m.get("risk_flags_catch_rate_pct"),
            "calibration": m.get("calibration"),
            "mode_promotion_progress": m.get("mode_promotion_progress"),
            "mode_samples": m.get("mode_samples"),
            "reward": m.get("reward"),
            "avg_prediction_error": m.get("avg_prediction_error"),
        }
    except Exception:
        twin_observability = {}
    phase2_metrics: dict[str, Any] = {}
    try:
        from lumina_core.birth.phase2_autonomy.metrics import compute_phase2_metrics_snapshot

        phase2_metrics = compute_phase2_metrics_snapshot(window_hours=24)
    except Exception:
        phase2_metrics = {"empty": True, "phase2_proposals_total": 0}
    capital_aperture: dict[str, Any] = {}
    try:
        from lumina_core.risk.capital_aperture_lineage import (
            aperture_lineage_integrity_snapshot,
        )

        capital_aperture = aperture_lineage_integrity_snapshot(
            Path(__file__).resolve().parents[2],
            audit_limit=100,
        )
    except Exception:
        capital_aperture = {"error": "aperture_snapshot_unavailable"}
    return {
        "twin_decisions": twin,
        "gate_rejections": gate,
        "shadow_runs": shadow,
        "daily_pnl_trend": daily_pnl,
        "perfect_birth_kpis": {
            "twin_accuracy_latest": twin_accuracy,
            "autonomy_rollup_latest": autonomy_rollup,
            "shadow_twin_alignment_latest": shadow_align,
            "twin_observability": twin_observability,
            "phase2_autonomy": phase2_metrics,
        },
        "twin_observability": twin_observability,
        "phase2_autonomy": phase2_metrics,
        "phase2_decisions_recent": phase2_recent,
        "capital_aperture_lineage": capital_aperture,
    }

async def get_capital_aperture(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """H1 aperture integrity: lineage coverage + strict-mode contract."""
    _check_api_key(x_api_key)
    from lumina_core.risk.capital_aperture_lineage import aperture_lineage_integrity_snapshot
    from lumina_core.risk.aperture_guard import STRICT_MODES

    from lumina_core.risk.capital_aperture_lineage import capital_aperture_residual_report

    snap = aperture_lineage_integrity_snapshot(
        Path(__file__).resolve().parents[2],
        audit_limit=200,
    )
    residual = snap.get("residual") or capital_aperture_residual_report()
    return {
        "ok": True,
        "strict_modes": sorted(STRICT_MODES),
        "lineage": snap,
        "h1": {
            "coverage_target_pct": snap.get("target_coverage_pct"),
            "coverage_meets_h1_goal": snap.get("coverage_meets_h1_goal"),
            "coverage_meets_phase2_goal": snap.get("coverage_meets_phase2_goal"),
            "lineage_coverage_pct": snap.get("lineage_coverage_pct"),
            "residual": residual,
        },
        "policy": {
            "strict_missing_lineage": "reject_at_admission",
            "soft_missing_lineage": "synthetic_ctx_for_observability",
            "legacy_skip_admission_flag": "stripped_and_logged",
            "real_apply_bypass": "forbidden",
            "durable_decision_log": "state/decision_log.jsonl on admit and reject",
            "single_non_bypassable_aperture": True,
            "fabric_is_transport_only": True,
        },
    }

async def get_monitoring_diagnostics(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """JSONL tails and workspace paths for Command Deck monitoring deep panel."""
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    repo = Path(__file__).resolve().parents[2]
    logs = repo / "logs"
    return {
        "paths": _monitoring_paths(),
        "structured_errors": _load_jsonl_file(logs / "structured_errors.jsonl", limit=25),
        "reasoning_latency": _load_jsonl_file(
            state / "monitoring_reasoning_latency.jsonl", limit=50
        ),
        "model_load_times": _load_jsonl_file(
            state / "monitoring_model_load_times.jsonl", limit=50
        ),
        "twin_training": _load_jsonl_file(state / "monitoring_twin_training.jsonl", limit=20),
        "gate_rejections": _load_jsonl_file(
            state / "monitoring_gate_rejections.jsonl", limit=30
        ),
    }

async def get_workspace_snapshot(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """System overview snapshot (monitoring tab A/B parity)."""
    _check_api_key(x_api_key)
    state = _repo_state_dir()
    repo = Path(__file__).resolve().parents[2]
    progress = _load_json_file(state / "lumina_birth_progress.json")
    if not progress:
        progress = _load_json_file(state / "first_boot_progress.json")
    config_payload = _load_json_file(repo / "config.yaml") or {}
    runtime_metrics = _load_json_file(state / "monitoring_runtime_metrics.json") or {}
    sim_state = _load_json_file(state / "lumina_sim_state.json") or {}
    return {
        "paths": _monitoring_paths(),
        "first_boot_progress": progress,
        "runtime_metrics": runtime_metrics,
        "sim_state": sim_state,
        "config_mode": str(config_payload.get("mode", "sim")),
        "config_first_boot": config_payload.get("first_boot") if isinstance(
            config_payload.get("first_boot"), dict
        ) else {},
    }

async def get_react_dashboard_status(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Embedded React dashboard URL readiness (Streamlit iframe parity)."""
    _check_api_key(x_api_key)
    try:
        from lumina_os.monitoring.dashboard_helpers import DashboardPaths, embedded_react_ui_status
    except ImportError:
        return {
            "ready": False,
            "reason": "dashboard_views_unavailable",
            "react_url": os.getenv("LUMINA_REACT_DASHBOARD_URL", "").strip()
            or f"http://127.0.0.1:{os.getenv('LUMINA_REACT_DASHBOARD_PORT', '5173')}",
        }

    repo = Path(__file__).resolve().parents[2]
    base_url = os.getenv("LUMINA_BACKEND_URL", "http://127.0.0.1:8000").strip()
    paths = DashboardPaths(repo)
    status = embedded_react_ui_status(base_url, paths)
    return status if isinstance(status, dict) else {"ready": False, "react_url": ""}

async def get_admin_setup_snapshot(
    x_api_key: Optional[str] = Header(None),
) -> dict[str, Any]:
    """Read-only admin metrics (Streamlit admin tab parity)."""
    _check_api_key(x_api_key)
    from lumina_launcher.core.blank_reset import DELETE_TARGETS, PRESERVED_STATE_FILES, WIPE_DIRECTORIES

    repo = Path(__file__).resolve().parents[2]
    state = repo / "state"
    env_path = repo / ".env"
    config_path = repo / "config.yaml"

    env_subset: dict[str, str] = {}
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in {
                "TRADE_MODE",
                "LUMINA_MODE",
                "INSTRUMENT",
                "DASHBOARD_ENABLED",
                "LUMINA_RUNTIME_TRACE",
            }:
                env_subset[key] = "***" if "KEY" in key or "TOKEN" in key else value.strip()

    setup_complete = _load_json_file(state / "lumina_setup_complete.json") or {}
    config_yaml = _load_json_file(config_path) or {}
    first_boot = config_yaml.get("first_boot") if isinstance(config_yaml.get("first_boot"), dict) else {}

    return {
        "setup_completed": bool(setup_complete.get("completed")),
        "runtime_mode": env_subset.get("LUMINA_MODE") or env_subset.get("TRADE_MODE") or "unknown",
        "configured_first_boot_trades": first_boot.get("training_trades"),
        "setup_complete_json": setup_complete,
        "config_yaml_subset": {
            "mode": config_yaml.get("mode"),
            "first_boot": first_boot,
        },
        "env_subset": env_subset,
        "reset_manifest": {
            "wipe_directories": list(WIPE_DIRECTORIES),
            "delete_targets": list(DELETE_TARGETS),
            "preserved_state_files": list(PRESERVED_STATE_FILES),
        },
    }
