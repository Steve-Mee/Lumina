"""Wipe listed Birth-v1 training artifacts without importing archived birth code."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

PRESERVED_STATE_FILES = (
    "hardware_snapshot.json",
    "launcher_admin_password.json",
    "model_catalog_state.json",
)

GENESIS_DELETE_TARGETS = (
    "state/lumina_setup_complete.json",
    "state/lumina_setup_status.json",
    "state/first_boot_user_configured.flag",
    "state/lumina_daytrading_bible.json",
    "state/lumina_birth_cache_manifest.json",
    "state/lumina_genesis_charter.json",
)

GENESIS_WIPE_DIRECTORIES = ("state/birth_enrichment_cache",)

TICK_CACHE_DELETE_TARGETS = (
    "state/lumina_birth_ticks_cache.jsonl",
    "state/lumina_birth_split_cache.json",
    "state/lumina_birth_cache_manifest.json",
)

TICK_CACHE_WIPE_DIRECTORIES = ("state/birth_enrichment_cache",)

POST_BIRTH_MATURATION_DELETE_TARGETS = (
    "state/lumina_maturity_progress.json",
    "state/monitoring_evolution_metrics.jsonl",
    "state/monitoring_twin_training.jsonl",
    "state/monitoring_twin_decisions.jsonl",
    "state/evolution_log.jsonl",
    "state/evolution_lifecycle.jsonl",
    "state/evolution_rollout_history.jsonl",
    "state/lumina_evolution_proof.json",
    "state/perfect_birth_complete.flag",
    "state/perfect_birth_complete.json",
    "state/perfect_birth_last_attempt.json",
    "state/phase2_sim_campaign.json",
    "state/twin_birth_readiness.json",
)

FOUNDATION_EXIT_DELETE_TARGETS = (
    "state/lumina_birth_foundation_receipts.json",
    "state/lumina_birth_fitness_vector.json",
    "state/dna_registry.jsonl",
    "state/dna_registry.json",
    "state/dna_registry.sqlite3",
    "state/lumina_evolution_proof.json",
    "state/perfect_birth_complete.flag",
    "state/perfect_birth_complete.json",
    "state/perfect_birth_last_attempt.json",
    "state/champion_freeze_telegram_pending.json",
    "state/milestone_notified.json",
    "state/twin_birth_readiness.json",
    "state/phase2_sim_campaign.json",
    "state/lumina_meta_milestones.jsonl",
)

BIRTH_DELETE_TARGETS = (
    "reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip",
    "reports/birth_cloud_run/artifacts/birth_exit_pi_star.json",
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
    "state/lumina_maturity_progress.json",
    "state/lumina_birth_cache_manifest.json",
    "state/metrics.db",
    "lumina_os/state/metrics.db",
    "lumina_agents/ppo/lumina_ppo_policy.zip",
    "lumina_agents/ppo/lumina_ppo_policy_practice.zip",
    *FOUNDATION_EXIT_DELETE_TARGETS,
)

BIRTH_GLOB_PATTERNS = (
    "lumina_agents/ppo/lumina_ppo_policy_birth_*.zip",
    "lumina_agents/ppo/birth_best_*.zip",
    "lumina_agents/ppo/birth_champion_*.zip",
    "journal/simulator/lumina_birth_training_*.json",
    "state/monitoring_*.jsonl",
    "state/dna_registry.sqlite3*",
)

POST_BIRTH_GLOB_PATTERNS = (
    "state/monitoring_evolution*.jsonl",
    "state/monitoring_twin_*.jsonl",
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


def _delete_relative_targets(
    workspace_root: Path,
    *,
    skip_relative: frozenset[str] = frozenset(),
) -> list[str]:
    removed: list[str] = []
    for relative in BIRTH_DELETE_TARGETS:
        if relative in skip_relative:
            continue
        rel = _unlink_path(workspace_root / relative, workspace_root)
        if rel:
            removed.append(rel)
    return removed


def _delete_glob_targets(
    workspace_root: Path,
    patterns: tuple[str, ...] = BIRTH_GLOB_PATTERNS,
) -> list[str]:
    removed: list[str] = []
    for pattern in patterns:
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


def _tick_cache_skip_set(*, preserve_tick_cache: bool) -> frozenset[str]:
    if not preserve_tick_cache:
        return frozenset()
    return frozenset(TICK_CACHE_DELETE_TARGETS)


def birth_certificate_issued(workspace_root: Path | str) -> bool:
    root = Path(workspace_root).resolve()
    if (root / "state" / "lumina_birth_completed.flag").is_file():
        return True
    cert = root / "state" / "lumina_birth_certificate.json"
    return cert.is_file()


def clear_post_birth_maturation_only(workspace_root: Path | str) -> BirthResetResult:
    root = Path(workspace_root).resolve()
    removed: list[str] = []
    for relative in POST_BIRTH_MATURATION_DELETE_TARGETS:
        rel = _unlink_path(root / relative, root)
        if rel:
            removed.append(rel)
    removed.extend(_delete_glob_targets(root, POST_BIRTH_GLOB_PATTERNS))
    return BirthResetResult(
        success=True,
        message="Post-birth maturation data cleared.",
        removed=sorted(set(removed)),
        preserved=[],
    )


def clear_birth_training_state(
    workspace_root: Path | str,
    *,
    wipe_logs: bool = True,
    wipe_journal: bool = True,
    wipe_genesis: bool = True,
    preserve_tick_cache: bool = False,
) -> BirthResetResult:
    """Unlink listed artifacts. Does not import archived Birth-v1 packages."""
    root = Path(workspace_root).resolve()
    removed: list[str] = []
    preserved: list[str] = []
    skip_targets = _tick_cache_skip_set(preserve_tick_cache=preserve_tick_cache)

    if not wipe_genesis:
        for name in PRESERVED_STATE_FILES:
            path = root / "state" / name
            if path.exists():
                preserved.append(str(path.relative_to(root)))
        for relative in GENESIS_DELETE_TARGETS:
            path = root / relative
            if path.exists():
                preserved.append(str(path.relative_to(root)))
    if preserve_tick_cache:
        for relative in TICK_CACHE_DELETE_TARGETS:
            path = root / relative
            if path.exists():
                preserved.append(str(path.relative_to(root)))

    removed.extend(_delete_relative_targets(root, skip_relative=skip_targets))
    removed.extend(_delete_glob_targets(root))
    if wipe_logs:
        removed.extend(_wipe_directory_contents(root / "logs", root))
        removed.extend(_wipe_directory_contents(root / "lumina_os" / "logs", root))
    if wipe_journal:
        removed.extend(_wipe_directory_contents(root / "journal" / "simulator", root))

    return BirthResetResult(
        success=True,
        message="Birth-v1 training artifacts cleared (archived engine not invoked).",
        removed=sorted(set(removed)),
        preserved=sorted(set(preserved)),
    )
