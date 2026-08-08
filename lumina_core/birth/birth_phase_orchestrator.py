"""Birth phase top-level orchestration (extracted from engine).

Thin coordinator: bootstrap → data/policy → certificate resume → curriculum/complete.
Phase implementations live in sibling modules (Wave D god-surface extract).
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_phase_bootstrap import bootstrap_birth_phase
from lumina_core.birth.birth_phase_certificate_gate import (
    certificate_fast_path_eligible as _certificate_fast_path_eligible,
)
from lumina_core.birth.birth_phase_certificate_resume import try_certificate_fast_path_resume
from lumina_core.birth.birth_phase_data_policy import prepare_birth_data_and_policy
from lumina_core.birth.birth_phase_train_complete import run_curriculum_and_complete
from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate  # noqa: F401
from lumina_core.birth.progress import read_birth_progress, write_birth_progress  # noqa: F401
from lumina_core.birth.remediation import reconstruct_checkpoint_from_progress  # noqa: F401
from lumina_core.first_boot_progress import ensure_first_boot_hardware_profile  # noqa: F401

# Back-compat aliases for tests/monkeypatches that reference this façade module.
__all__ = [
    "run_birth_phase",
    "_certificate_fast_path_eligible",
    "ensure_first_boot_hardware_profile",
    "evaluate_holdout_certificate",
    "read_birth_progress",
    "reconstruct_checkpoint_from_progress",
    "write_birth_progress",
]


def run_birth_phase(
    host: Any,
    *,
    target_trades: int | None = None,
    max_real_days: int = 365,
    prefer_real_data_only: bool = True,
    chunk_size: int = 50_000,
    ppo_update_timesteps: int = 25_000,
    force: bool = False,
    practice_mode: bool = False,
    reuse_existing_policy: bool | None = None,
    reuse_data_manifest: bool = False,
    expand_data: bool = False,
) -> dict[str, Any]:
    _ = reuse_data_manifest  # reserved; data pipeline reads host state
    boot = bootstrap_birth_phase(
        host,
        target_trades=target_trades,
        max_real_days=max_real_days,
        prefer_real_data_only=prefer_real_data_only,
        chunk_size=chunk_size,
        ppo_update_timesteps=ppo_update_timesteps,
        force=force,
        practice_mode=practice_mode,
        reuse_existing_policy=reuse_existing_policy,
        expand_data=expand_data,
    )
    data = prepare_birth_data_and_policy(host, boot)
    if data.early_return is not None:
        return data.early_return
    # Propagate checkpoint_phase repairs into boot for certificate resume
    if data.checkpoint_phase and data.checkpoint_phase != boot.checkpoint_phase:
        boot.checkpoint_phase = data.checkpoint_phase
    cert = try_certificate_fast_path_resume(host, boot, data)
    if cert is not None:
        return cert
    return run_curriculum_and_complete(host, boot, data)
