"""Single source of truth for wiping Birth Phase training artifacts."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from lumina_core.birth.buffer_persist import clear_buffer
from lumina_core.birth.checkpoint import clear_checkpoint
from lumina_core.birth.tick_cache_persist import clear_ticks_cache

logger = logging.getLogger(__name__)

PRESERVED_STATE_FILES = (
    "lumina_setup_complete.json",
    "lumina_setup_status.json",
    "hardware_snapshot.json",
    "launcher_admin_password.json",
    "model_catalog_state.json",
    "first_boot_user_configured.flag",
)

BIRTH_DELETE_TARGETS = (
    "state/lumina_birth_completed.flag",
    "state/lumina_birth_practice_completed.flag",
    "state/first_boot_completed.flag",
    "state/lumina_birth_progress.json",
    "state/first_boot_progress.json",
    "state/lumina_birth_checkpoint.json",
    "state/first_boot_checkpoint.json",
    "state/first_boot_pause_requested",
    "state/first_boot_go_to_bot.flag",
    "state/lumina_birth_certificate.json",
    "state/lumina_birth_buffer.jsonl",
    "state/lumina_birth_ticks_cache.jsonl",
    "state/lumina_birth_split_cache.json",
    "state/birth_news_cache.json",
    "state/birth_runner.json",
    "state/ppo_policy_metadata.json",
    "state/hardware_profile.json",
    "state/birth_regime_prior.json",
    "state/ppo_training_log.jsonl",
    "state/monitoring_debug_training_process.json",
    "state/monitoring_runtime_metrics.json",
    "state/trade_reconciler_status.json",
    "lumina_os/state/metrics.db",
    "lumina_agents/ppo/lumina_ppo_policy.zip",
    "lumina_agents/ppo/lumina_ppo_policy_practice.zip",
)

BIRTH_GLOB_PATTERNS = (
    "lumina_agents/ppo/lumina_ppo_policy_birth_*.zip",
    "journal/simulator/lumina_birth_training_*.json",
    "state/monitoring_*.jsonl",
)

BIRTH_WIPE_DIRECTORIES = (
    "logs",
    "journal/simulator",
    "lumina_os/logs",
)


@dataclass(slots=True)
class BirthResetResult:
    success: bool
    message: str
    removed: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)


def _unlink_path(target: Path, workspace_root: Path) -> str | None:
    if not target.exists():
        return None
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        else:
            target.unlink(missing_ok=True)
        return str(target.relative_to(workspace_root))
    except OSError:
        logger.warning("birth_reset.unlink_failed path=%s", target, exc_info=True)
        return None


def _delete_relative_targets(workspace_root: Path) -> list[str]:
    removed: list[str] = []
    for relative in BIRTH_DELETE_TARGETS:
        rel = _unlink_path(workspace_root / relative, workspace_root)
        if rel:
            removed.append(rel)
    return removed


def _delete_glob_targets(workspace_root: Path) -> list[str]:
    removed: list[str] = []
    for pattern in BIRTH_GLOB_PATTERNS:
        for match in workspace_root.glob(pattern):
            rel = _unlink_path(match, workspace_root)
            if rel:
                removed.append(rel)
    return removed


def _wipe_directory_contents(path: Path, workspace_root: Path) -> list[str]:
    removed: list[str] = []
    path.mkdir(parents=True, exist_ok=True)
    for child in list(path.iterdir()):
        rel = _unlink_path(child, workspace_root)
        if rel:
            removed.append(rel)
    return removed


def clear_birth_training_state(
    workspace_root: Path | str,
    *,
    wipe_logs: bool = True,
    wipe_journal: bool = True,
) -> BirthResetResult:
    """Remove all Birth Phase training artifacts; preserve setup/genesis config."""
    root = Path(workspace_root).resolve()
    removed: list[str] = []
    preserved: list[str] = []

    for name in PRESERVED_STATE_FILES:
        path = root / "state" / name
        if path.exists():
            preserved.append(str(path.relative_to(root)))

    clear_checkpoint(root)
    clear_buffer(root)
    clear_ticks_cache(root)
    removed.extend(_delete_relative_targets(root))
    removed.extend(_delete_glob_targets(root))

    if wipe_logs:
        removed.extend(_wipe_directory_contents(root / "logs", root))
        removed.extend(_wipe_directory_contents(root / "lumina_os" / "logs", root))
    if wipe_journal:
        removed.extend(_wipe_directory_contents(root / "journal" / "simulator", root))

    return BirthResetResult(
        success=True,
        message="Birth training state cleared.",
        removed=sorted(set(removed)),
        preserved=sorted(set(preserved)),
    )


def main() -> int:
    """CLI entry for operator scripts (e.g. reset_lumina_blank_state.ps1)."""
    import argparse

    from lumina_launcher.services.workspace_root import resolve_birth_workspace_root

    parser = argparse.ArgumentParser(description="Clear Birth Phase training artifacts.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="LUMINA workspace root (default: auto-detect)",
    )
    parser.add_argument("--no-logs", action="store_true", help="Skip wiping logs directories")
    parser.add_argument("--no-journal", action="store_true", help="Skip wiping journal/simulator")
    args = parser.parse_args()
    root = resolve_birth_workspace_root(args.workspace)
    result = clear_birth_training_state(
        root,
        wipe_logs=not args.no_logs,
        wipe_journal=not args.no_journal,
    )
    print(result.message)
    print(f"Removed {len(result.removed)} artifact(s).")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
