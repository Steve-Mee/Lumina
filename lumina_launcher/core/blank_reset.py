"""Blank-reset service for returning launcher to post-setup state."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from lumina_launcher.core.birth_reset import (
    BIRTH_DELETE_TARGETS,
    BIRTH_WIPE_DIRECTORIES,
    PRESERVED_STATE_FILES,
    clear_birth_training_state,
)

WIPE_DIRECTORIES = BIRTH_WIPE_DIRECTORIES
DELETE_TARGETS = BIRTH_DELETE_TARGETS

BACKUP_TARGETS = (
    "state",
    "logs",
    "journal/simulator",
    "lumina_os/logs",
    *BIRTH_DELETE_TARGETS,
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


def _wipe_state_selective(state_dir: Path) -> tuple[list[str], list[str]]:
    removed: list[str] = []
    preserved: list[str] = []
    state_dir.mkdir(parents=True, exist_ok=True)
    keep = set(PRESERVED_STATE_FILES)
    keep.update(Path(relative).name for relative in (
        "state/lumina_setup_complete.json",
        "state/lumina_setup_status.json",
        "state/first_boot_user_configured.flag",
        "state/lumina_daytrading_bible.json",
        "state/lumina_birth_cache_manifest.json",
    ))
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

    birth_result = clear_birth_training_state(
        root,
        wipe_logs=True,
        wipe_journal=True,
        wipe_genesis=False,
    )
    removed_paths: list[str] = list(birth_result.removed)
    state_removed, state_preserved = _wipe_state_selective(root / "state")
    removed_paths.extend(state_removed)

    return BlankResetResult(
        success=True,
        message="Post-setup blank reset completed.",
        backup_path=backup_root,
        preserved=state_preserved,
        removed=removed_paths,
    )
