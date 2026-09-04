"""G0/G1 isolated genesis workspace + new certified-schema tape."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.genesis_cloud_const import (
    FORBIDDEN_TICKS_SHA16,
    GENESIS_ART,
    GENESIS_FIXTURE_SEED,
    GENESIS_HOLDOUT_PCT,
    GENESIS_INSTRUMENT,
    GENESIS_ROOT,
    GENESIS_START_PRICE,
    GENESIS_WORK,
    OLD_PARENT_ZIPS,
    REPO_ROOT,
)
from lumina_core.birth.genesis_cloud_protocol import (
    GenesisProtocolError,
    assert_genesis_seed,
    refuse_old_ticks_sha,
)
from lumina_core.birth.synthetic_cloud_fixture import (
    SOURCE_LABEL,
    CloudFixtureSpec,
    persist_cloud_fixture,
    write_fixture_sidecar,
)
from lumina_core.birth.tick_cache_persist import load_ticks_cache


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_old_parent_zips(repo: Path | None = None) -> dict[str, str]:
    root = repo or REPO_ROOT
    art = root / "reports" / "birth_cloud_run" / "artifacts"
    out: dict[str, str] = {}
    for name in OLD_PARENT_ZIPS:
        path = art / name
        out[name] = file_sha256(path) if path.is_file() else ""
    return out


def assert_old_zips_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_old_parent_zips(repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise GenesisProtocolError(f"old parent zip mutated: {name}")


def prepare_genesis_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "genesis_cloud_run"
    if repo is None:
        work, art, reports = GENESIS_WORK, GENESIS_ART, GENESIS_ROOT
    else:
        work, art, reports = root / "workspace", root / "artifacts", root
    work.mkdir(parents=True, exist_ok=True)
    (work / "state").mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    src = (repo or REPO_ROOT) / "config.yaml"
    dest = work / "config.yaml"
    shutil.copy2(src, dest)
    overlay_sim_config(dest)
    catalog = (repo or REPO_ROOT) / "lumina_model_catalog.json"
    if catalog.is_file():
        shutil.copy2(catalog, work / "lumina_model_catalog.json")
    os.environ["LUMINA_CONFIG"] = str(dest.resolve())
    os.environ["VOICE_ENABLED"] = "false"
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    return reports, work, art


def overlay_sim_config(path: Path) -> None:
    """SIM overlay: NQ primary, faster checkpoints. Does not touch stage/cert floors."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError("workspace config.yaml is not a mapping")
    raw["mode"] = "sim"
    trading = dict(raw.get("trading") or {})
    trading["instrument"] = GENESIS_INSTRUMENT
    raw["trading"] = trading
    first_boot = dict(raw.get("first_boot") or {})
    first_boot["prefer_real_data_only"] = True
    first_boot["allow_minimal_synthetic_fallback"] = False
    first_boot["max_real_days"] = int(FOUNDATION_HISTORY_START_DAYS)
    raw["first_boot"] = first_boot
    birth = dict(raw.get("birth_v2") or {})
    birth["prefer_real_data_only"] = True
    birth["max_real_days"] = int(FOUNDATION_HISTORY_START_DAYS)
    cur = dict(birth.get("curriculum") or {})
    cur["checkpoint_interval_sec"] = min(int(cur.get("checkpoint_interval_sec") or 600), 20)
    birth["curriculum"] = cur
    raw["birth_v2"] = birth
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def persist_genesis_fixture(
    work: Path,
    art: Path,
    *,
    rth_bar_seconds: int = 10,
    eth_bar_seconds: int = 60,
) -> dict[str, Any]:
    assert_genesis_seed(GENESIS_FIXTURE_SEED)
    spec = CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(FOUNDATION_HISTORY_START_DAYS),
        holdout_pct=GENESIS_HOLDOUT_PCT,
        start_price=GENESIS_START_PRICE,
        seed=GENESIS_FIXTURE_SEED,
        rth_bar_seconds=int(rth_bar_seconds),
        eth_bar_seconds=int(eth_bar_seconds),
    )
    result = persist_cloud_fixture(work, spec=spec)
    sidecar = art / "01_genesis_fixture_manifest.json"
    write_fixture_sidecar(sidecar, result.fixture_manifest)
    payload = dict(result.fixture_manifest)
    payload["rth_bar_seconds"] = int(rth_bar_seconds)
    payload["eth_bar_seconds"] = int(eth_bar_seconds)
    payload["real_data_pct"] = 0.0
    payload["fixture_seed"] = GENESIS_FIXTURE_SEED
    assert_genesis_fixture(work, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def assert_genesis_fixture(work: Path, manifest: dict[str, Any]) -> None:
    source = str(manifest.get("source") or "")
    if source != SOURCE_LABEL:
        raise GenesisProtocolError(f"fixture source {source!r} != {SOURCE_LABEL}")
    pct = float(manifest.get("real_data_pct") or 0.0)
    if pct != 0.0:
        raise GenesisProtocolError("real_data_pct must be 0.0 on synthetic")
    ticks = int(manifest.get("tick_count") or 0)
    if ticks < 1000:
        raise GenesisProtocolError(f"tick_count {ticks} < 1000")
    days = int(manifest.get("days") or 0)
    if days < 86:
        raise GenesisProtocolError(f"actual days {days} < 86")
    regimes = list(manifest.get("holdout_regimes") or [])
    if len(regimes) < 3:
        raise GenesisProtocolError(f"holdout regimes {regimes} < 3")
    train_hash = str(manifest.get("hash") or manifest.get("train_hash") or "")
    refuse_old_ticks_sha(train_hash)
    if train_hash == FORBIDDEN_TICKS_SHA16:
        raise GenesisProtocolError("train_hash collided with old 7e86c2bb tape")
    cached = load_ticks_cache(work)
    if len(cached) < 1000:
        raise GenesisProtocolError("on-disk tick cache thinner than 1000")
    prev = ""
    for row in cached:
        ts = str(row.get("timestamp") or "")
        if not ts or ts <= prev:
            raise GenesisProtocolError("raw timestamps not strictly monotonic")
        prev = ts
        if float(row["bid"]) >= float(row["ask"]):
            raise GenesisProtocolError("bid < ask violated")
        if str(row.get("source")) != SOURCE_LABEL:
            raise GenesisProtocolError("tick source label drifted")


__all__ = [
    "assert_genesis_fixture",
    "assert_old_zips_untouched",
    "file_sha256",
    "overlay_sim_config",
    "persist_genesis_fixture",
    "prepare_genesis_trees",
    "snapshot_old_parent_zips",
]
