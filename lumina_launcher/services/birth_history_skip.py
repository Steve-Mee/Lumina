"""History-preflight skip rules. Physics (torch/SB3) is a separate T=0 gate."""

from __future__ import annotations


def skip_launcher_history_preflight(
    *,
    force: bool,
    practice_mode: bool,
    continue_training: bool,
    reuse_data: bool,
    checkpoint_exists: bool,
    certified_cache_exists: bool = False,
) -> bool:
    """Whether launcher may skip live Fabric/NT history probe before engine start.

    Fresh certified starts still probe. Resume/reuse with an on-disk checkpoint
    trusts engine cache + fail-closed cold load — no second parallel data gate.
    Certified tick-cache + ``reuse_data`` (no checkpoint) is the Stage-1 physics
    restart path: history is already on disk, so AMBER Fabric must not block.
    """
    if practice_mode:
        return True
    if force:
        return False
    if checkpoint_exists and (continue_training or reuse_data):
        return True
    return bool(reuse_data and certified_cache_exists and not continue_training)
