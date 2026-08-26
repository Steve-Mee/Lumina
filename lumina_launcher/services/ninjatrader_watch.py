"""Detect NinjaTrader updates and re-run Fabric diagnostic (fail-closed halt)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from lumina_launcher.services.fabric_connection_diagnostics import run_fabric_connection_diagnostics
from lumina_launcher.services.fabric_link_certificate import (
    is_halt_active,
    read_nt_fingerprint,
    set_halt,
    write_certificate,
    write_nt_fingerprint,
)

logger = logging.getLogger(__name__)


def default_nt_exe_candidates() -> list[Path]:
    paths: list[Path] = []
    override = str(os.getenv("NINJATRADER8_PATH") or "").strip()
    if override:
        paths.append(Path(override))
    pf = os.environ.get("ProgramFiles") or r"C:\Program Files"
    paths.append(Path(pf) / "NinjaTrader 8" / "bin" / "NinjaTrader.exe")
    pfx86 = os.environ.get("ProgramFiles(x86)")
    if pfx86:
        paths.append(Path(pfx86) / "NinjaTrader 8" / "bin" / "NinjaTrader.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        paths.append(Path(local) / "Programs" / "NinjaTrader 8" / "bin" / "NinjaTrader.exe")
    return paths


def resolve_nt_exe() -> Path | None:
    for p in default_nt_exe_candidates():
        if p.is_file():
            return p
    return None


def fingerprint_nt_exe(path: Path) -> dict[str, Any]:
    st = path.stat()
    return {
        "path": str(path),
        "size": st.st_size,
        "mtime_ns": getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
    }


def check_ninjatrader_update_and_reprobe(
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    """If NT fingerprint changed, invalidate via re-diagnostic; halt on non-green."""
    exe = resolve_nt_exe()
    result: dict[str, Any] = {
        "nt_installed": exe is not None,
        "changed": False,
        "overall": None,
        "halt": is_halt_active(workspace_root),
        "action": "none",
    }
    if exe is None:
        return result

    fp = fingerprint_nt_exe(exe)
    prev = read_nt_fingerprint(workspace_root)
    write_nt_fingerprint(fp, workspace_root)

    if prev and (
        prev.get("path") != fp.get("path")
        or prev.get("size") != fp.get("size")
        or prev.get("mtime_ns") != fp.get("mtime_ns")
    ):
        result["changed"] = True
        result["action"] = "reprobe"
        report = run_fabric_connection_diagnostics(include_safe_mode=True)
        result["overall"] = report.overall
        if report.overall == "green":
            try:
                from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

                token = str(fabric_secret_read(heal=True).token or "").strip()
            except Exception:
                token = ""
            hist = next((c for c in report.checks if c.id == "historical_bars"), None)
            write_certificate(
                overall="green",
                target=report.target,
                token=token,
                workspace_root=workspace_root,
                extra={
                    "historical_bars": getattr(hist, "status", None) or "pass",
                    "checks": [{"id": c.id, "status": c.status} for c in report.checks],
                },
            )
            result["action"] = "certified"
        else:
            set_halt(
                reason="ninjatrader_update_fabric_failed",
                workspace_root=workspace_root,
                detail={"overall": report.overall, "summary": report.summary},
            )
            result["halt"] = True
            result["action"] = "halt"
            result["needs_repair"] = True
            result["repair_hint"] = (
                "NinjaTrader was updated or reinstalled. "
                "Click “Repair NinjaTrader connection” in Setup — Lumina will reinstall the bridge."
            )
            logger.warning("NT update re-probe failed overall=%s — FABRIC HALT (repair available)", report.overall)
    return result
