"""Hash-epoch counter for Foundation stages (ADR-0046).

An epoch is one completed rollout on a given ``train_hash``. Hitting the
stage cap expands data (new hash resets the counter). This is not
``max_rollouts=2`` — the stage may keep rolling after expand.
"""

from __future__ import annotations

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_stages import foundation_eval_only, foundation_max_epochs


def note_foundation_epoch(
    *,
    previous_hash: str,
    current_hash: str,
    previous_count: int,
) -> tuple[int, str]:
    """Return ``(epoch_count, hash)`` after one completed rollout."""
    cur = str(current_hash or "").strip()
    prev = str(previous_hash or "").strip()
    if not cur:
        return max(0, int(previous_count)), prev
    if cur != prev:
        return 1, cur
    return max(0, int(previous_count)) + 1, cur


def epoch_cap_exceeded(stage: CurriculumStage, epoch_count: int) -> bool:
    """Hash-epoch expand/freeze is S4-only. S5 is eval-only; S1–S3 use certified rollouts."""
    if foundation_eval_only(stage):
        return False
    if stage != CurriculumStage.STAGE4_VIABLE_PLANT:
        return False
    return int(epoch_count) > foundation_max_epochs(stage)


__all__ = ["epoch_cap_exceeded", "note_foundation_epoch"]
