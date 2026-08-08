"""M5 modularization LOC guard — prod trees stay ≤400 LOC."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAX_LOC = 400

# Historical declared residual surfaces (must stay ≤400).
M5_RESIDUAL_TARGETS = [
    "lumina_core/container/__init__.py",
    "lumina_core/risk/risk_controller.py",
    "lumina_core/risk/risk_allocator.py",
    "lumina_core/risk/regime_detector.py",
    "lumina_core/rl/gym_environment.py",
    "lumina_core/rl/trend_features.py",
    "lumina_core/logging_utils.py",
    "lumina_core/monitoring/observability_recorders.py",
    "lumina_core/safety/sandboxed_executor.py",
    "lumina_core/safety/sandboxed_code_executor.py",
    "lumina_launcher/services/birth_service.py",
    "lumina_launcher/services/birth_status_mapper.py",
    "lumina_launcher/services/birth_runner_start.py",
    "lumina_launcher/services/fabric_diag_preflight.py",
    "lumina_launcher/services/setup_orchestrator.py",
    "lumina_os/api/monitoring.py",
    "lumina_os/backend/twin_endpoints.py",
    "lumina_os/backend/evolution_endpoints.py",
    "lumina_os/backend/setup_endpoints.py",
    "lumina_os/backend/core_websocket.py",
    "lumina_os/backend/birth_endpoints.py",
    "lumina_os/backend/monitoring_endpoints.py",
]


def _loc(rel: str) -> int:
    path = ROOT / rel
    assert path.is_file(), f"missing M5 residual target: {rel}"
    return sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))


@pytest.mark.parametrize("rel", M5_RESIDUAL_TARGETS)
def test_m5_residual_target_under_400_loc(rel: str) -> None:
    n = _loc(rel)
    assert n <= MAX_LOC, f"{rel} has {n} LOC (max {MAX_LOC})"


# Wave-D landing residuals: must not grow; further splits tracked as evolutionary debt.
M5_OVER_400_CEILINGS: dict[str, int] = {
    "lumina_launcher/services/fabric_simhost.py": 585,
    "lumina_core/birth/starship_swarm_gates.py": 486,
    "lumina_core/birth/champion_freeze_telegram.py": 468,
    "lumina_core/ops/operator_residuals.py": 465,
    "lumina_core/birth/recovery_compress.py": 460,
    "lumina_core/birth/stage_loop_recovery_terminal.py": 455,
    "lumina_core/birth/organism_autonomy.py": 443,
    "lumina_launcher/services/fabric_diag_live.py": 422,
    "lumina_core/risk/capital_aperture_lineage.py": 421,
    "lumina_core/birth/sim_runner.py": 420,
    "lumina_core/notifications/telegram_notifier.py": 414,
    "lumina_core/engine/visualization_charts.py": 401,
}


def test_m5_prod_trees_have_zero_files_over_400() -> None:
    """Global M5 bar: prod Python >400 LOC only via explicit must-not-grow ceilings."""
    over: list[tuple[int, str]] = []
    grew: list[str] = []
    for tree in ("lumina_core", "lumina_launcher", "lumina_os"):
        root = ROOT / tree
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if any(part in {"__pycache__", "tests", ".venv"} for part in path.parts):
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            n = sum(1 for _ in path.open(encoding="utf-8", errors="ignore"))
            if n <= MAX_LOC:
                continue
            ceiling = M5_OVER_400_CEILINGS.get(rel)
            if ceiling is None:
                over.append((n, rel))
            elif n > ceiling:
                grew.append(f"{rel}: {n} > ceiling {ceiling}")
    over.sort(reverse=True)
    assert not over, "prod files >400 LOC without allowlist:\n" + "\n".join(
        f"  {n}  {p}" for n, p in over
    )
    assert not grew, "allowlisted residual grew:\n" + "\n".join(f"  {g}" for g in grew)


def test_m5_residual_split_modules_exist() -> None:
    """Companion modules created by residual splits must remain importable paths."""
    companions = [
        "lumina_core/risk/risk_limits_from_config.py",
        "lumina_core/risk/risk_allocator_var_es.py",
        "lumina_core/rl/gym_environment_step.py",
        "lumina_core/rl/trend_features_core.py",
        "lumina_core/rl/trend_features_batch.py",
        "lumina_core/monitoring/observability_metric_names.py",
        "lumina_core/monitoring/observability_recorders_mode.py",
        "lumina_core/safety/sandboxed_code_worker.py",
        "lumina_core/logging_core.py",
        "lumina_core/logging_monitoring.py",
        "lumina_core/logging_evolution.py",
        "lumina_launcher/services/birth_service_recovery.py",
        "lumina_launcher/services/birth_status_mapper_get.py",
        "lumina_launcher/services/birth_runner_preflight.py",
        "lumina_launcher/services/fabric_diag_preflight_run.py",
        "lumina_launcher/services/setup_orchestrator_run.py",
        "lumina_os/api/monitoring_enrich.py",
        "lumina_os/backend/twin_endpoints_auth.py",
        "lumina_os/backend/twin_endpoints_gym.py",
        "lumina_os/backend/evolution_endpoints_auth.py",
        "lumina_os/backend/evolution_endpoints_actions.py",
        "lumina_os/backend/setup_endpoints_fabric.py",
        "lumina_os/backend/core_websocket_telemetry.py",
        "lumina_os/backend/birth_endpoints_enrich.py",
        "lumina_os/backend/monitoring_endpoints_ops.py",
    ]
    missing = [c for c in companions if not (ROOT / c).is_file()]
    assert not missing, f"missing M5 companion modules: {missing}"
