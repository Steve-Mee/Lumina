"""Detect NinjaTrader updates and keep the Fabric addon compilable (zero-IT)."""

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
    """Keep Custom compilable; on NT.exe change re-probe and halt only if still red.

    Always injects/retargets, copies Newtonsoft.Json into Custom, and adds it to
    Config.xml <References> (NT compiler SSOT) so NT's own compiler succeeds
    after an installer rewrite. Rebuilds Custom.dll only when NT is stopped.
    Never kills NinjaTrader — Repair remains the explicit close path.
    """
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

    changed = bool(
        prev
        and (
            prev.get("path") != fp.get("path")
            or prev.get("size") != fp.get("size")
            or prev.get("mtime_ns") != fp.get("mtime_ns")
        )
    )
    result["changed"] = changed

    from lumina_launcher.services.fabric_heal import (
        ensure_custom_compile_ready,
        is_ninjatrader_running,
    )

    # Zero-IT: installer may rewrite csproj without changing NT.exe fingerprint
    # (already recorded). Always keep Lumina + well-known refs in the csproj.
    try:
        heal_files = ensure_custom_compile_ready(build_if_nt_stopped=True)
    except Exception as exc:
        logger.warning("NT custom auto-heal failed: %s", exc)
        heal_files = {
            "ok": False,
            "csproj_changed": False,
            "built": False,
            "nt_running": False,
            "inject": {"status": f"error:{exc}"},
            "build": {"status": "error"},
        }
    result["auto_heal"] = {
        "ok": bool(heal_files.get("ok")),
        "csproj_changed": bool(heal_files.get("csproj_changed")),
        "built": bool(heal_files.get("built")),
        "nt_running": bool(heal_files.get("nt_running")),
        "inject": (heal_files.get("inject") or {}).get("status"),
        "build": (heal_files.get("build") or {}).get("status"),
        "isolated": (heal_files.get("build") or {}).get("isolated") or [],
    }
    if heal_files.get("csproj_changed") or heal_files.get("built"):
        logger.info("NT custom auto-heal: %s", result["auto_heal"])

    if not changed:
        if heal_files.get("built") or heal_files.get("csproj_changed"):
            result["action"] = "healed"
        return result

    result["action"] = "reprobe"
    report = run_fabric_connection_diagnostics(include_safe_mode=False, allow_live_order_probe=False)
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
        return result

    nt_up = bool(heal_files.get("nt_running")) or is_ninjatrader_running()
    files_ready = bool(heal_files.get("ok")) and (
        bool(heal_files.get("built")) or bool(heal_files.get("csproj_changed"))
    )
    if files_ready and not nt_up:
        # Addon files repaired; NT is simply closed. Do not halt — operator
        # starts NT themselves; NT's compiler now has Newtonsoft + Lumina.
        result["action"] = "healed_waiting_nt"
        result["repair_hint"] = (
            "NinjaTrader is closed. Start NinjaTrader — Lumina already repaired the addon."
        )
        logger.info("NT update files healed while NT stopped — waiting for operator start")
        return result

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
