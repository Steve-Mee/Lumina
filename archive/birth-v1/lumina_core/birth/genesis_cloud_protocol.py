"""Fail-closed genesis protocol: refuse old body, refuse REAL=yes on synthetic."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from lumina_core.birth.genesis_cloud_const import (
    FORBIDDEN_PARENT_ZIP_NAMES,
    FORBIDDEN_TICKS_SHA16,
    G6_TAG,
    GENESIS_FIXTURE_SEED,
)


class GenesisProtocolError(RuntimeError):
    """Genesis first-life protocol violation (fail-closed)."""


def assert_genesis_seed(seed: int) -> int:
    n = int(seed)
    if n != GENESIS_FIXTURE_SEED:
        raise GenesisProtocolError(f"genesis seed must be {GENESIS_FIXTURE_SEED}, got {n}")
    return n


def refuse_old_parent_as_input(path: Path | str | None) -> None:
    if path is None:
        return
    target = Path(path)
    name = target.name
    if name in FORBIDDEN_PARENT_ZIP_NAMES:
        raise GenesisProtocolError(f"refused old parent zip name as input: {name}")
    posix = target.as_posix()
    if "birth_cloud_run" in posix and posix.endswith(".zip"):
        raise GenesisProtocolError(f"refused old birth_cloud_run zip as input: {posix}")


def refuse_old_ticks_sha(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if not text:
        return text
    if text == FORBIDDEN_TICKS_SHA16 or text.startswith("7e86c2bb"):
        raise GenesisProtocolError(f"refused ticks sha {FORBIDDEN_TICKS_SHA16} as this tape (old body)")
    return text


def real_flag_for_source(*, source: str, real_data_pct: float) -> str:
    """Genesis never prints REAL=yes. Synthetic + 0% real is not a certificate."""
    _ = source
    _ = real_data_pct
    return "no"


def assert_real_not_yes_on_synthetic(flags: Mapping[str, Any]) -> None:
    source = str(flags.get("source") or flags.get("tick_source") or "")
    real = str(flags.get("REAL") or "").strip().lower()
    pct = float(flags.get("real_data_pct") or 0.0)
    synthetic = source in {"synthetic_cloud_fixture", "genesis_cloud_ladder"} or pct < 95.0
    if synthetic and real in {"yes", "true", "1"}:
        raise GenesisProtocolError("protocol crime: REAL=yes on synthetic tape")


def locked_g6_tag() -> str:
    return G6_TAG


def empty_genesis_flags() -> dict[str, Any]:
    return {
        "source": "genesis_cloud_ladder",
        "fixture_seed": GENESIS_FIXTURE_SEED,
        "fixture_train_hash": "",
        "real_data_pct": 0.0,
        "birth_exited": False,
        "birth_status": "",
        "newborn_zip_sha256": "",
        "mark_eyes_child_sha256": "",
        "learn_called": False,
        "actual_timesteps": 0,
        "G5_tag": "GENESIS_BIRTH_ONLY",
        "G6_tag": G6_TAG,
        "evolution_proof_stamped": False,
        "REAL": "no",
        "playground": False,
        "hook_default": False,
        "used_old_path_early": False,
        "used_old_parent_zip": False,
        "overall": "GENESIS_CLOUD_LADDER SHADOW_MEASURE",
    }


def compose_genesis_flags(payload: Mapping[str, Any]) -> dict[str, Any]:
    flags = empty_genesis_flags()
    flags.update(dict(payload))
    flags["REAL"] = real_flag_for_source(
        source=str(flags.get("source") or ""),
        real_data_pct=float(flags.get("real_data_pct") or 0.0),
    )
    flags["G6_tag"] = locked_g6_tag()
    flags["evolution_proof_stamped"] = False
    flags["playground"] = False
    flags["hook_default"] = False
    flags["used_old_path_early"] = False
    flags["used_old_parent_zip"] = False
    assert_real_not_yes_on_synthetic(flags)
    if str(flags.get("G6_tag")) != G6_TAG:
        raise GenesisProtocolError("G6 tag must stay REAL_DOOR_LOCKED")
    return flags


__all__ = [
    "GenesisProtocolError",
    "assert_genesis_seed",
    "assert_real_not_yes_on_synthetic",
    "compose_genesis_flags",
    "empty_genesis_flags",
    "locked_g6_tag",
    "real_flag_for_source",
    "refuse_old_parent_as_input",
    "refuse_old_ticks_sha",
]
