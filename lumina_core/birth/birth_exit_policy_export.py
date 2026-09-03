"""Deterministic birth-exit π* export so Awakening can load frozen weights.

Saves the Stage-5 pass policy BEFORE light polish. Zip lives under reports/
artifacts (not gitignored ``lumina_agents/ppo/*.zip``). Missing file = fail-closed
load, never a fake STABLE grind.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_exit_policy_export")

PI_STAR_ZIP_NAME = "birth_exit_pi_star.zip"
PI_STAR_META_NAME = "birth_exit_pi_star.json"
EXPORT_SITE = "lumina_core/birth/foundation_complete.py:export_birth_exit_pi_star"


def resolve_pi_star_path(workspace_root: Path | str | None) -> Path:
    root = Path(workspace_root) if workspace_root else Path.cwd()
    if root.name == "workspace" and root.parent.name == "birth_cloud_run":
        return root.parent / "artifacts" / PI_STAR_ZIP_NAME
    return root / "reports" / "birth_cloud_run" / "artifacts" / PI_STAR_ZIP_NAME


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_meta(zip_path: Path, *, source: str, extra: dict[str, Any] | None = None) -> Path:
    meta = {
        "schema": "birth_exit_pi_star_v1",
        "path": str(zip_path),
        "sha256": file_sha256(zip_path) if zip_path.is_file() else "",
        "bytes": int(zip_path.stat().st_size) if zip_path.is_file() else 0,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "export_site": EXPORT_SITE,
        "pre_polish": True,
    }
    if extra:
        meta.update(extra)
    sidecar = zip_path.with_name(PI_STAR_META_NAME)
    sidecar.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return sidecar


def export_birth_exit_pi_star(host: Any) -> Path | None:
    """Persist frozen S5-pass weights. Must run before ``final_birth_polish``."""
    trainer = getattr(host, "ppo_trainer", None)
    root = getattr(host, "workspace_root", None)
    if trainer is None or root is None:
        logger.warning("birth.pi_star.export_skipped missing trainer_or_root")
        return None
    dest = resolve_pi_star_path(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    save = getattr(trainer, "save_weights", None) or getattr(
        trainer, "save_final_birth_policy", None
    )
    if not callable(save):
        logger.warning("birth.pi_star.export_skipped no_save_hook")
        return None
    save(str(dest))
    if not dest.is_file():
        logger.warning("birth.pi_star.export_missing path=%s", dest)
        return None
    _write_meta(dest, source="s5_pass_pre_polish")
    logger.info("birth.pi_star.exported path=%s sha16=%s", dest, file_sha256(dest)[:16])
    return dest


def candidate_frozen_paths(workspace_root: Path | str | None) -> list[Path]:
    """Search order: reports export, then workspace zip (gitignored, may be absent)."""
    root = Path(workspace_root) if workspace_root else Path.cwd()
    out = [resolve_pi_star_path(root)]
    if root.name == "workspace" and root.parent.name == "birth_cloud_run":
        out.append(root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip")
    else:
        out.append(root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip")
        cloud_ws = root / "reports" / "birth_cloud_run" / "workspace"
        out.append(cloud_ws / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip")
    seen: set[str] = set()
    unique: list[Path] = []
    for path in out:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def resolve_frozen_policy_path(workspace_root: Path | str | None) -> Path | None:
    for path in candidate_frozen_paths(workspace_root):
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def load_frozen_policy(path: Path | str) -> Any | None:
    """PPO.load only. Never creates a fresh policy. Missing/corrupt → None."""
    target = Path(path)
    if not target.is_file():
        return None
    try:
        from stable_baselines3 import PPO

        return PPO.load(str(target))
    except Exception as exc:
        logger.warning("birth.pi_star.load_failed path=%s err=%s", target, exc)
        return None


__all__ = [
    "EXPORT_SITE",
    "PI_STAR_META_NAME",
    "PI_STAR_ZIP_NAME",
    "candidate_frozen_paths",
    "export_birth_exit_pi_star",
    "file_sha256",
    "load_frozen_policy",
    "resolve_frozen_policy_path",
    "resolve_pi_star_path",
]
