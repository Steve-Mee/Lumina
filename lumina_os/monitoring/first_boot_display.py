"""First-boot display helpers for monitoring (no Streamlit)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_os.monitoring.dashboard_helpers import DashboardPaths, resolve_workspace_root_from_this_module

_ACTIVE_TRAINING_STAGES = frozenset(
    {
        "detected",
        "loading_data",
        "training_running",
        "pipeline_boot",
        "parallel_simulation",
        "ppo_training",
    }
)


@dataclass(frozen=True)
class MonitoringPaths:
    workspace_root: Path
    state_dir: Path
    logs_dir: Path
    journal_sim_dir: Path
    first_boot_progress: Path
    first_boot_legacy_progress: Path
    first_boot_flag: Path
    first_boot_legacy_flag: Path
    policy_zip: Path
    ppo_policy_metadata: Path
    approval_twin_model: Path
    twin_decisions: Path
    twin_training: Path
    shadow_runs: Path
    runtime_metrics: Path
    gate_rejections: Path
    reasoning_latency: Path
    model_load_times: Path
    daily_pnl_history: Path
    debug_training_process: Path
    structured_errors: Path
    full_log: Path
    sim_state: Path
    config_yaml: Path
    embedded_ui_index: Path

    @classmethod
    def resolve(cls, workspace_root: Path | None = None) -> MonitoringPaths:
        root = (workspace_root or resolve_workspace_root_from_this_module()).resolve()
        dp = DashboardPaths(root)
        state = dp.state_dir
        return cls(
            workspace_root=root,
            state_dir=state,
            logs_dir=root / "logs",
            journal_sim_dir=root / "journal" / "simulator",
            first_boot_progress=state / "lumina_birth_progress.json",
            first_boot_legacy_progress=state / "first_boot_progress.json",
            first_boot_flag=state / "lumina_birth_completed.flag",
            first_boot_legacy_flag=state / "first_boot_completed.flag",
            policy_zip=root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip",
            ppo_policy_metadata=state / "ppo_policy_metadata.json",
            approval_twin_model=state / "approval_twin_model.json",
            twin_decisions=state / "monitoring_twin_decisions.jsonl",
            twin_training=state / "monitoring_twin_training.jsonl",
            shadow_runs=state / "evolution_shadow_runs.json",
            runtime_metrics=state / "monitoring_runtime_metrics.json",
            gate_rejections=state / "monitoring_gate_rejections.jsonl",
            reasoning_latency=state / "monitoring_reasoning_latency.jsonl",
            model_load_times=state / "monitoring_model_load_times.jsonl",
            daily_pnl_history=state / "monitoring_daily_pnl.jsonl",
            debug_training_process=state / "monitoring_debug_training_process.json",
            structured_errors=root / "logs" / "structured_errors.jsonl",
            full_log=root / "logs" / "lumina_full_log.csv",
            sim_state=dp.runtime_state,
            config_yaml=dp.config_yaml,
            embedded_ui_index=dp.embedded_ui_index,
        )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def first_boot_completion_display(paths: MonitoringPaths, progress: dict[str, Any]) -> tuple[str, str]:
    stage = str(progress.get("stage", "")).strip().lower()
    if stage in _ACTIVE_TRAINING_STAGES:
        return "In progress", "n/a"
    if stage in {"completed", "completed_waiting_user_action"}:
        ts = (
            paths.first_boot_flag.read_text(encoding="utf-8").strip()
            if paths.first_boot_flag.exists()
            else (
                paths.first_boot_legacy_flag.read_text(encoding="utf-8").strip()
                if paths.first_boot_legacy_flag.exists()
                else str(progress.get("timestamp", "n/a"))
            )
        )
        return "Yes", ts
    if stage == "failed":
        return "Failed", "n/a"
    if stage == "deferred_calendar":
        return "Deferred", "n/a"
    if (paths.first_boot_flag.exists() or paths.first_boot_legacy_flag.exists()) and paths.policy_zip.exists():
        ts = (
            paths.first_boot_flag.read_text(encoding="utf-8").strip()
            if paths.first_boot_flag.exists()
            else paths.first_boot_legacy_flag.read_text(encoding="utf-8").strip()
        )
        return "Yes", ts
    return "No", "n/a"


def first_boot_progress_fraction(progress: dict[str, Any]) -> float:
    raw = progress.get("progress_pct")
    if raw is not None:
        try:
            pct = float(raw)
            if 0.0 <= pct <= 100.0:
                return pct / 100.0
        except (TypeError, ValueError):
            pass
    stage = str(progress.get("stage", "unknown"))
    stage_to_progress = {
        "detected": 10,
        "loading_data": 30,
        "pipeline_boot": 40,
        "parallel_simulation": 60,
        "ppo_training": 82,
        "training_running": 70,
        "completed": 100,
        "completed_waiting_user_action": 100,
        "failed": 100,
    }
    return stage_to_progress.get(stage, 0) / 100.0


def first_boot_historical_days_display(progress: dict[str, Any]) -> int:
    for key in ("actual_real_days_loaded", "estimated_real_days"):
        if progress.get(key) is not None:
            return _safe_int(progress.get(key))
    return 0
