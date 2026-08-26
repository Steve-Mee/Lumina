"""Fail-closed Fabric DLL integrity checks (deploy / heal / scorecard).

Product NtBridge must contain NT Account + historical + live MD types.
Standalone/stub builds (often ~12–20 KB) are rejected.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Full Release NtBridge with NT Account + hist + live is ~50 KB+.
# Stubs / FABRIC_STANDALONE thin builds are ~12–30 KB and lack order/history types.
NT_BRIDGE_MIN_BYTES = 40_000
FABRIC_CORE_MIN_BYTES = 100_000

# ASCII type markers embedded in the IL metadata of a complete product build.
NT_BRIDGE_REQUIRED_MARKERS: tuple[str, ...] = (
    "FabricNtHost",
    "NtAccountOrderGateway",
    "NtHistoricalDataProvider",
    "NtLiveMarketDataProvider",
)


def sha256_file(path: Path, *, limit: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        if limit is None:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            h.update(fh.read(int(limit)))
    return h.hexdigest()


def _ascii_contains(data: bytes, needle: str) -> bool:
    try:
        return needle.encode("ascii") in data
    except Exception:
        return False


def verify_nt_bridge_dll(path: Path | str) -> dict[str, Any]:
    """Return integrity report for Lumina.Fabric.NtBridge.dll.

    ok=True only when size floor + required type markers are present.
    """
    p = Path(path)
    report: dict[str, Any] = {
        "ok": False,
        "path": str(p),
        "exists": p.is_file(),
        "size": 0,
        "sha256": "",
        "markers": {},
        "missing_markers": [],
        "reason": "",
    }
    if not p.is_file():
        report["reason"] = "missing_file"
        return report
    try:
        size = int(p.stat().st_size)
    except OSError as exc:
        report["reason"] = f"stat_failed:{exc}"
        return report
    report["size"] = size
    if size < NT_BRIDGE_MIN_BYTES:
        report["reason"] = f"too_small:{size}<{NT_BRIDGE_MIN_BYTES}"
        return report
    try:
        data = p.read_bytes()
    except OSError as exc:
        report["reason"] = f"read_failed:{exc}"
        return report
    report["sha256"] = hashlib.sha256(data).hexdigest()
    markers = {m: _ascii_contains(data, m) for m in NT_BRIDGE_REQUIRED_MARKERS}
    report["markers"] = markers
    missing = [m for m, present in markers.items() if not present]
    report["missing_markers"] = missing
    if missing:
        report["reason"] = "missing_types:" + ",".join(missing)
        return report
    report["ok"] = True
    report["reason"] = "ok"
    return report


def verify_fabric_core_dll(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    report: dict[str, Any] = {
        "ok": False,
        "path": str(p),
        "exists": p.is_file(),
        "size": 0,
        "sha256": "",
        "reason": "",
    }
    if not p.is_file():
        report["reason"] = "missing_file"
        return report
    try:
        size = int(p.stat().st_size)
        report["size"] = size
        report["sha256"] = sha256_file(p)
    except OSError as exc:
        report["reason"] = f"stat_failed:{exc}"
        return report
    if size < FABRIC_CORE_MIN_BYTES:
        report["reason"] = f"too_small:{size}<{FABRIC_CORE_MIN_BYTES}"
        return report
    report["ok"] = True
    report["reason"] = "ok"
    return report


def pick_best_nt_bridge(candidates: list[Path]) -> Path | None:
    """Choose the largest integrity-ok NtBridge among candidates."""
    best: Path | None = None
    best_size = -1
    for c in candidates:
        if c is None or not c.is_file():
            continue
        rep = verify_nt_bridge_dll(c)
        if not rep.get("ok"):
            logger.debug("fabric.integrity.reject %s reason=%s", c, rep.get("reason"))
            continue
        sz = int(rep.get("size") or 0)
        if sz > best_size:
            best = c
            best_size = sz
    return best


def collect_bridge_candidates(workspace_root: Path) -> list[Path]:
    root = Path(workspace_root)
    names = ("Lumina.Fabric.NtBridge.dll", "LuminaNt8AddOn.dll")
    dirs = (
        root / "integrations/ninjatrader8/LuminaNt8AddOn/bin/Release/net48",
        root / "integrations/ninjatrader8/deploy/AddOns",
        root / "tauri-app/src-tauri/resources/fabric",
    )
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        for name in names:
            p = d / name
            key = str(p.resolve()) if p.exists() else str(p)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    return out


def dual_tree_bridge_drift(custom_dirs: list[Path]) -> dict[str, Any]:
    """Compare NtBridge hashes across NT Custom trees."""
    rows: list[dict[str, Any]] = []
    hashes: set[str] = set()
    for custom in custom_dirs:
        bridge = Path(custom) / "Lumina.Fabric.NtBridge.dll"
        rep = verify_nt_bridge_dll(bridge)
        rows.append(rep)
        if rep.get("sha256"):
            hashes.add(str(rep["sha256"]))
    return {
        "trees": rows,
        "unique_hashes": len(hashes),
        "drift": len(hashes) > 1,
        "all_ok": all(bool(r.get("ok")) for r in rows if r.get("exists")),
        "any_stub": any(
            r.get("exists") and not r.get("ok") for r in rows
        ),
    }


__all__ = [
    "NT_BRIDGE_MIN_BYTES",
    "FABRIC_CORE_MIN_BYTES",
    "NT_BRIDGE_REQUIRED_MARKERS",
    "sha256_file",
    "verify_nt_bridge_dll",
    "verify_fabric_core_dll",
    "pick_best_nt_bridge",
    "collect_bridge_candidates",
    "dual_tree_bridge_drift",
]
