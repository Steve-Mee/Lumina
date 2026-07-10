"""Birth status fields for genesis charter, meta milestones, and autonomy metrics."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_AUTONOMY_PREFIXES = ("death_spiral_", "policy_swarm_", "oos_proxy_")


def _extract_autonomy_metrics(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key, value in raw.items():
        key_str = str(key)
        if key_str.startswith(_AUTONOMY_PREFIXES):
            out[key_str] = value
    return out


def maturity_status_fields(workspace_root: Path | str) -> dict[str, Any]:
    """Load maturity artifacts for birth status / API enrichment."""
    root = Path(workspace_root)
    from lumina_core.birth.checkpoint import load_checkpoint_state
    from lumina_core.birth.genesis_charter import resolve_genesis_charter
    from lumina_core.evolution.meta_milestones import load_meta_milestones

    charter = resolve_genesis_charter(root)
    milestones = [item.to_dict() for item in load_meta_milestones(root)]

    ckpt = load_checkpoint_state(root)
    autonomy_sources: list[dict[str, Any]] = []
    if isinstance(ckpt, dict):
        for key in ("stage_metrics", "autonomy_metrics"):
            block = ckpt.get(key)
            if isinstance(block, dict):
                autonomy_sources.append(block)
        autonomy_sources.append(ckpt)

    autonomy_metrics: dict[str, Any] = {}
    for source in autonomy_sources:
        autonomy_metrics.update(_extract_autonomy_metrics(source))

    progress_autonomy = _extract_autonomy_metrics(
        ckpt if isinstance(ckpt, dict) else None
    )
    autonomy_metrics.update(progress_autonomy)

    return {
        "genesis_charter": charter,
        "meta_milestones": milestones,
        "autonomy_metrics": autonomy_metrics or None,
    }