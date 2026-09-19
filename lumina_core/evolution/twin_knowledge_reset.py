"""Wipe Twin judgment DNA + base training. Never touches Birth sacred artefacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

WIPE_CONFIRM_TOKEN = "WIPE_TWIN_KNOWLEDGE"

TWIN_KNOWLEDGE_FILENAMES: tuple[str, ...] = (
    "twin_base_training.json",
    "twin_birth_readiness.json",
    "steve_values_registry.sqlite3",
    "steve_values_registry.sqlite3-wal",
    "steve_values_registry.sqlite3-shm",
    "steve_values_registry.jsonl",
    "approval_twin_model.json",
    "twin_pending_questions.json",
    "twin_decision_notify_pending.json",
)

_SACRED_NAME_FRAGMENTS: frozenset[str] = frozenset(
    {
        "lumina_birth_ticks_cache",
        "lumina_birth_certificate",
        "lumina_birth_checkpoint",
        "lumina_birth_progress",
        "lumina_birth_split_cache",
        "fabric_link_certificate",
        "config.yaml",
        "lumina_genesis_charter",
    }
)


def _assert_not_sacred(path: Path) -> None:
    lowered = path.name.lower()
    for fragment in _SACRED_NAME_FRAGMENTS:
        if fragment in lowered:
            raise RuntimeError(f"Twin knowledge wipe refused sacred path: {path.name}")


def wipe_twin_knowledge(
    *,
    state_dir: Path | str,
    confirm: str,
    extra_paths: tuple[Path, ...] = (),
) -> dict[str, Any]:
    """Delete Twin labels, model, pending queue, and base-training session.

    Birth tick-cache, certificates, Fabric, and config are forbidden targets.
    """
    token = str(confirm or "").strip()
    if token != WIPE_CONFIRM_TOKEN:
        raise ValueError(
            f"Twin knowledge wipe requires confirm={WIPE_CONFIRM_TOKEN!r} "
            "(this cannot be undone; Birth seal will block until you retrain)."
        )
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True)
    targets = [root / name for name in TWIN_KNOWLEDGE_FILENAMES]
    targets.extend(extra_paths)
    removed: list[str] = []
    missing: list[str] = []
    errors: list[str] = []
    for path in targets:
        _assert_not_sacred(path)
        if not path.exists():
            missing.append(path.name)
            continue
        try:
            path.unlink()
            removed.append(path.name)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
    if errors:
        raise RuntimeError("Twin knowledge wipe incomplete: " + "; ".join(errors))
    return {
        "ok": True,
        "wiped": True,
        "confirm": WIPE_CONFIRM_TOKEN,
        "removed": removed,
        "already_absent": missing,
        "birth_ready": False,
        "base_trained": False,
        "message": (
            "Twin knowledge and base training wiped. Seal + Birth stay blocked "
            "until you retrain from zero. Birth tick-cache was not touched."
        ),
        "local_only": True,
    }
