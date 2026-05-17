"""Blank-reset service for returning launcher to post-setup state."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


PRESERVED_STATE_FILES = (
    "lumina_setup_complete.json",
    "lumina_setup_status.json",
    "hardware_snapshot.json",
    "launcher_admin_password.json",
    "model_catalog_state.json",
)

WIPE_DIRECTORIES = (
    "logs",
    "journal/simulator",
    "lumina_os/logs",
)

BACKUP_TARGETS = (
    "state",
    "logs",
    "journal/simulator",
    "lumina_os/logs",
    "lumina_os/state/metrics.db",
    "lumina_agents/ppo/lumina_ppo_policy.zip",
    "lumina_agents/ppo/lumina_ppo_policy_practice.zip",
    "state/lumina_birth_completed.flag",
    "state/lumina_birth_practice_completed.flag",
    "state/first_boot_completed.flag",
    "state/ppo_policy_metadata.json",
    "state/lumina_birth_progress.json",
    "state/first_boot_progress.json",
    "state/lumina_birth_checkpoint.json",
    "state/first_boot_checkpoint.json",
    "state/first_boot_user_configured.flag",
)

DELETE_TARGETS = (
    "lumina_os/state/metrics.db",
    "lumina_agents/ppo/lumina_ppo_policy.zip",
    "lumina_agents/ppo/lumina_ppo_policy_practice.zip",
    "state/lumina_birth_completed.flag",
    "state/lumina_birth_practice_completed.flag",
    "state/first_boot_completed.flag",
    "state/lumina_birth_progress.json",
    "state/first_boot_progress.json",
    "state/lumina_birth_checkpoint.json",
    "state/first_boot_checkpoint.json",
    "state/first_boot_pause_requested",
    "state/first_boot_user_configured.flag",
    "state/ppo_policy_metadata.json",
    "state/monitoring_debug_training_process.json",
    "state/trade_reconciler_status.json",
)


@dataclass(slots=True)
class BlankResetResult:
    success: bool
    message: str
    backup_path: Path | None
    preserved: list[str]
    removed: list[str]


def _copy_with_parents(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(source, destination)


def _backup_targets(workspace_root: Path, backup_root: Path) -> None:
    for relative in BACKUP_TARGETS:
        src = workspace_root / relative
        if not src.exists():
            continue
        _copy_with_parents(src, backup_root / relative)


def _wipe_directory_contents(path: Path) -> list[str]:
    removed: list[str] = []
    path.mkdir(parents=True, exist_ok=True)
    for child in list(path.iterdir()):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
        removed.append(str(child))
    return removed


def _wipe_state_selective(state_dir: Path) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    preserved: list[str] = []
    state_dir.mkdir(parents=True, exist_ok=True)
    keep = set(PRESERVED_STATE_FILES)
    for child in list(state_dir.iterdir()):
        if child.name in keep:
            preserved.append(str(child))
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
        removed.append(str(child))
    return removed, preserved


def _delete_targets(workspace_root: Path) -> list[str]:
    removed: list[str] = []
    for relative in DELETE_TARGETS:
        target = workspace_root / relative
        if not target.exists():
            continue
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        removed.append(str(target))
    return removed


def run_post_setup_blank_reset(
    workspace_root: Path,
    *,
    stop_runtime: Callable[[], tuple[bool, str]] | None = None,
) -> BlankResetResult:
    root = workspace_root.resolve()
    if stop_runtime is not None:
        ok, msg = stop_runtime()
        if not ok:
            return BlankResetResult(
                success=False,
                message=f"Runtime stop failed: {msg}",
                backup_path=None,
                preserved=[],
                removed=[],
            )

    backup_root = root / "backups" / f"reset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_root.mkdir(parents=True, exist_ok=True)
    _backup_targets(root, backup_root)

    removed_paths: list[str] = []
    for relative in WIPE_DIRECTORIES:
        removed_paths.extend(_wipe_directory_contents(root / relative))
    state_removed, state_preserved = _wipe_state_selective(root / "state")
    removed_paths.extend(state_removed)
    removed_paths.extend(_delete_targets(root))

    return BlankResetResult(
        success=True,
        message="Post-setup blank reset completed.",
        backup_path=backup_root,
        preserved=state_preserved,
        removed=removed_paths,
    )
