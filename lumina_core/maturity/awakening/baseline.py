"""First Watch baseline. The frozen plant's holdout book, hashed, not a pass stamp."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "first_watch_baseline_v1"
SEAL_REL = Path("state") / "lumina_first_watch_baseline.json"


def seal_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / SEAL_REL


def load_first_watch_seal(workspace_root: Path | str) -> dict[str, Any]:
    path = seal_path(workspace_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def seal_matches_disk(workspace_root: Path | str) -> dict[str, Any]:
    """The seal, or empty when the zip or either ledger no longer matches its hash."""
    from lumina_core.birth.birth_exit_policy_export import file_sha256, resolve_pi_star_path
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_LEDGER_NAME,
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
        live_child_zip,
    )

    root = Path(workspace_root)
    seal = load_first_watch_seal(root)
    if str(seal.get("schema") or "") != SCHEMA:
        return {}
    weight = str(seal.get("weight_sha256") or "")
    init = str(seal.get("init_weight_sha256") or "")
    zip_sha = str(seal.get("zip_sha256") or "")
    if not weight or weight != init or not zip_sha:
        return {}
    art = artifacts_dir(root)
    child = art / INCUMBENT_LEDGER_NAME
    parent = art / INCUMBENT_PARENT_LEDGER_NAME
    if not _sha_file(child, str(seal.get("ledger_sha256") or "")):
        return {}
    if not _sha_file(parent, str(seal.get("parent_ledger_sha256") or "")):
        return {}
    live = live_child_zip(root)
    birth = resolve_pi_star_path(root)
    if not live.is_file() or not birth.is_file():
        return {}
    if file_sha256(live) != zip_sha or file_sha256(birth) != zip_sha:
        return {}
    return seal


def _sha_file(path: Path, expected: str) -> bool:
    if not expected or not path.is_file() or path.stat().st_size <= 0:
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected


def seal_first_watch(workspace_root: Path | str) -> dict[str, Any]:
    """Write the seal from the frozen incumbent ledger. Refuses a missing book."""
    from lumina_core.io.atomic_fs import atomic_write_text
    from lumina_core.maturity.awakening.progress import load_awakening_progress
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_LEDGER_NAME,
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
    )

    root = Path(workspace_root)
    art = artifacts_dir(root)
    child = art / INCUMBENT_LEDGER_NAME
    parent = art / INCUMBENT_PARENT_LEDGER_NAME
    if not child.is_file() or child.stat().st_size <= 0:
        raise RuntimeError("first watch baseline ledger missing")
    if not parent.is_file() or parent.stat().st_size <= 0:
        raise RuntimeError("first watch parent ledger missing")
    prog = load_awakening_progress(root)
    payload = {
        "schema": SCHEMA,
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "run_id": str(prog.get("run_id") or ""),
        "zip_sha256": str(prog.get("child_sha") or ""),
        "weight_sha256": str(prog.get("child_weight_sha") or ""),
        "init_weight_sha256": str(prog.get("init_weight_sha") or ""),
        "ledger_sha256": hashlib.sha256(child.read_bytes()).hexdigest(),
        "parent_ledger_sha256": hashlib.sha256(parent.read_bytes()).hexdigest(),
        "n_b": int(prog.get("n_b") or 0),
        "occupancy_at_nb": prog.get("occupancy_at_nb"),
        "stable_class": str(prog.get("stable_class") or ""),
        "regime_observed": list(prog.get("regime_observed") or []),
        "constitution_violations": prog.get("constitution_violations"),
        "constitution_blocks": prog.get("constitution_blocks"),
        "paired_ci_low": prog.get("paired_ci_low"),
        "paired_delta": prog.get("paired_delta"),
        "note": "Baseline book. paired_ci_low is recorded and is not this seal's pass.",
    }
    if payload["weight_sha256"] != payload["init_weight_sha256"] or not payload["weight_sha256"]:
        raise RuntimeError("first watch seal refused a substituted plant")
    from lumina_core.birth.birth_exit_policy_export import file_sha256, resolve_pi_star_path
    from lumina_core.maturity.phase_runners.awakening_shot import live_child_zip

    live = live_child_zip(root)
    birth = resolve_pi_star_path(root)
    if not live.is_file() or not birth.is_file():
        raise RuntimeError("first watch seal refused a missing zip")
    live_sha = file_sha256(live)
    if live_sha != file_sha256(birth) or live_sha != payload["zip_sha256"]:
        raise RuntimeError("first watch seal refused a zip that is not the Birth plant")
    atomic_write_text(seal_path(root), json.dumps(payload, ensure_ascii=True, indent=2) + "\n")
    return payload
