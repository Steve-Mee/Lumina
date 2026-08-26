"""Zero-IT Fabric heal / install pipeline for NinjaTrader coupling.

Closes NT if needed, deploys bridge DLLs + source AddOn, optionally builds
NinjaTrader.Custom, launches NT, waits for host, runs dual-plane diagnostic.

Sim101 / localhost / fail-closed. Never enables REAL gateway.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

StepStatus = Literal["pass", "fail", "skip", "warn"]


def _fabric_secret_token() -> str:
    try:
        from lumina_core.broker.ninjatrader.fabric_secret import read as fabric_secret_read

        return str(fabric_secret_read(heal=True).token or "").strip()
    except Exception:
        return ""


@dataclass
class HealStep:
    id: str
    title: str
    status: StepStatus
    message: str
    user_message: str = ""
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HealReport:
    ok: bool
    overall: str  # green | amber | red | unknown
    steps: list[HealStep] = field(default_factory=list)
    needs_user: list[dict[str, str]] = field(default_factory=list)
    report: dict[str, Any] | None = None
    certified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "overall": self.overall,
            "steps": [s.to_dict() for s in self.steps],
            "needs_user": self.needs_user,
            "report": self.report,
            "certified": self.certified,
        }


def _nt_exe_candidates() -> list[Path]:
    from lumina_launcher.services.ninjatrader_watch import default_nt_exe_candidates

    return default_nt_exe_candidates()


def resolve_nt_exe() -> Path | None:
    from lumina_launcher.services.ninjatrader_watch import resolve_nt_exe as _r

    return _r()


def is_ninjatrader_running() -> bool:
    try:
        from lumina_launcher.services.fabric_simhost import is_ninjatrader_running as _is

        return bool(_is())
    except Exception:
        return False


def close_ninjatrader(*, force_after_sec: float = 8.0, reason: str = "explicit_repair") -> dict[str, Any]:
    """Graceful-then-force stop NinjaTrader.exe (Windows). Idempotent if not running.

    Code Red: every call is logged to %APPDATA%/LUMINA/nt-lifecycle.log.
    Must only be invoked from user-initiated Repair (or equivalent opt-in).
    """
    from lumina_launcher.services.nt_lifecycle import log_nt_lifecycle

    if not is_ninjatrader_running():
        log_nt_lifecycle("close_skipped", reason=reason, detail={"status": "not_running"})
        return {"ok": True, "status": "not_running", "killed": []}

    log_nt_lifecycle("close_begin", reason=reason, detail={"force_after_sec": force_after_sec})
    killed: list[int] = []
    if sys.platform == "win32":
        # Soft close
        try:
            subprocess.run(
                ["taskkill", "/IM", "NinjaTrader.exe"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("fabric.heal.soft_close_failed: %s", exc)

        deadline = time.time() + max(1.0, float(force_after_sec))
        while time.time() < deadline and is_ninjatrader_running():
            time.sleep(0.4)

        if is_ninjatrader_running():
            try:
                r = subprocess.run(
                    ["taskkill", "/IM", "NinjaTrader.exe", "/F", "/T"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                logger.info("fabric.heal.force_close rc=%s out=%s", r.returncode, (r.stdout or "")[:200])
            except (OSError, subprocess.TimeoutExpired) as exc:
                log_nt_lifecycle("close_failed", reason=reason, detail={"error": str(exc)})
                return {"ok": False, "status": "kill_failed", "message": str(exc), "killed": killed}
            time.sleep(0.6)

        # Settle so DLL locks release
        time.sleep(0.5)
        still = is_ninjatrader_running()
        result = {
            "ok": not still,
            "status": "stopped" if not still else "still_running",
            "killed": killed,
            "message": "NinjaTrader stopped" if not still else "NinjaTrader still running after taskkill",
        }
        log_nt_lifecycle("close_end", reason=reason, detail=result)
        return result

    log_nt_lifecycle("close_unsupported", reason=reason)
    return {"ok": False, "status": "unsupported_os", "message": "close_ninjatrader only on Windows"}


def launch_ninjatrader() -> dict[str, Any]:
    exe = resolve_nt_exe()
    if exe is None:
        return {"ok": False, "status": "not_installed", "message": "NinjaTrader 8 not found"}
    try:
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"ok": True, "status": "launched", "exe": str(exe)}
    except OSError as exc:
        return {"ok": False, "status": "launch_failed", "message": str(exc), "exe": str(exe)}


def _primary_custom_dir() -> Path | None:
    from lumina_launcher.services.fabric_bootstrap import ninjatrader_custom_candidates

    ranked = ninjatrader_custom_candidates()
    for c in ranked:
        if (c / "NinjaTrader.Custom.dll").is_file() or (c / "NinjaTrader.Custom.csproj").is_file():
            return c
        if any(c.glob("CrossTrade*.dll")):
            return c
    # Prefer first that has parent NT tree
    for c in ranked:
        if (c.parent.parent / "log").is_dir() or c.is_dir():
            return c
    return ranked[0] if ranked else None


def _sanitize_nt_custom_csproj(text: str) -> tuple[str, list[str]]:
    """Strip obj/ junk Compile entries that break NinjaScript (CS0579/CS2001).

    External ``dotnet build`` of NinjaTrader.Custom generates under ``obj\\``:
    - ``*.AssemblyAttributes.cs``
    - satellite ``*.resources.cs`` (per culture) with full [assembly:] attributes

    If those land in the main project Compile list (NT auto-add or stale csproj),
    they collide with root ``AssemblyInfo.cs`` → mass CS0579 in the editor.
    Never compile anything under ``obj\\`` into NinjaTrader.Custom.
    """
    import re

    notes: list[str] = []
    # Any Compile Include pointing at obj\... (AssemblyAttributes, resources.cs, etc.)
    pattern = re.compile(
        r'^\s*<Compile\s+Include="obj\\[^"]*"\s*/>\s*\r?\n',
        re.MULTILINE | re.IGNORECASE,
    )
    new_text, n = pattern.subn("", text)
    if n:
        notes.append(f"removed_{n}_obj_compile_includes")
        text = new_text

    # Ensure SDK/default globs cannot pull obj back in (pair with existing None/Page Remove).
    if 'Compile Remove="obj\\**"' not in text and "Compile Remove='obj\\**'" not in text:
        remove_block = (
            "  <ItemGroup>\n"
            '    <Compile Remove="obj\\**" />\n'
            '    <None Remove="obj\\**" />\n'
            '    <Page Remove="obj\\**" />\n'
            "  </ItemGroup>\n"
        )
        # Prefer merging into existing ItemGroup that already removes obj
        if '<None Remove="obj\\**"' in text or "<None Remove=\"obj\\**\"" in text:
            # Inject Compile Remove next to existing None Remove
            text2, n2 = re.subn(
                r'(<ItemGroup>\s*\r?\n)(\s*<None Remove="obj\\\*\*"\s*/>)',
                r'\1    <Compile Remove="obj\\**" />\n\2',
                text,
                count=1,
            )
            if n2:
                text = text2
                notes.append("added_compile_remove_obj")
            else:
                # Fallback: prepend Compile Remove line before first None Remove obj
                text = text.replace(
                    '<None Remove="obj\\**" />',
                    '<Compile Remove="obj\\**" />\n    <None Remove="obj\\**" />',
                    1,
                )
                notes.append("added_compile_remove_obj")
        elif "</Project>" in text:
            text = text.replace("</Project>", remove_block + "</Project>", 1)
            notes.append("added_obj_exclude_itemgroup")

    return text, notes


def clean_nt_custom_obj_pollution(custom: Path) -> dict[str, Any]:
    """Delete generated satellite/resources attribute sources under obj (NT F5 safety).

    NinjaTrader's editor may scan/add .cs files; leaving satellite resources.cs
    next to the project is a recurring CS0579 footgun after external builds.
    """
    obj = custom / "obj"
    removed: list[str] = []
    if not obj.is_dir():
        return {"ok": True, "removed": removed, "status": "no_obj"}

    patterns = (
        "**/*AssemblyAttributes.cs",
        "**/*.resources.cs",
        "**/NinjaTrader.Custom.resources.cs",
    )
    for pat in patterns:
        for p in obj.glob(pat):
            try:
                p.unlink()
                removed.append(str(p.relative_to(custom)))
            except OSError as exc:
                logger.warning("fabric.heal.obj_clean_failed %s: %s", p, exc)

    return {"ok": True, "removed": removed, "status": "cleaned" if removed else "nothing_to_clean"}


def inject_lumina_source_into_csproj(custom: Path) -> dict[str, Any]:
    """Ensure AddOns\\@LuminaFabricHost.cs is Compile-included in NinjaTrader.Custom.csproj."""
    csproj = custom / "NinjaTrader.Custom.csproj"
    if not csproj.is_file():
        return {"ok": False, "status": "no_csproj", "message": str(csproj)}

    text = csproj.read_text(encoding="utf-8", errors="replace")
    text, sanitize_notes = _sanitize_nt_custom_csproj(text)
    marker = "LuminaFabricHost"
    include_line = '    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />\n'
    # Also accept non-escaped form
    already = marker in text
    if not already:
        # Insert before first </ItemGroup> that has Compile includes, else before </Project>
        insert = include_line
        if "</ItemGroup>" in text:
            # Prefer ItemGroup that already has Compile Include
            idx = text.find("<Compile Include=")
            if idx >= 0:
                # find start of that ItemGroup line after previous newline
                line_start = text.rfind("\n", 0, idx) + 1
                text = text[:line_start] + insert + text[line_start:]
            else:
                text = text.replace("</Project>", f"  <ItemGroup>\n{insert}  </ItemGroup>\n</Project>", 1)
        else:
            text = text.replace("</Project>", f"  <ItemGroup>\n{insert}  </ItemGroup>\n</Project>", 1)

    if already and not sanitize_notes:
        return {"ok": True, "status": "already_present", "path": str(csproj)}

    backup = csproj.with_suffix(".csproj.bak_lumina_heal")
    try:
        if not backup.is_file():
            shutil.copy2(csproj, backup)
        csproj.write_text(text, encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "status": "write_failed", "message": str(exc)}
    status = "already_present" if already else "injected"
    if sanitize_notes:
        status = f"{status}+sanitized"
    return {
        "ok": True,
        "status": status,
        "path": str(csproj),
        "sanitize": sanitize_notes,
    }


def build_ninjatrader_custom(custom: Path) -> dict[str, Any]:
    """dotnet build NinjaTrader.Custom.csproj so source AddOn is in NinjaTrader.Custom.dll.

    Zero-IT path: end users should never open NinjaScript Editor / F5.
    Always sanitize csproj before/after and scrub obj pollution so NT's own
    compiler does not hit CS0579 (duplicate assembly attributes).
    """
    csproj = custom / "NinjaTrader.Custom.csproj"
    if not csproj.is_file():
        return {"ok": False, "status": "no_csproj", "message": "NinjaTrader.Custom.csproj missing"}

    def _write_sanitized() -> list[str]:
        try:
            text = csproj.read_text(encoding="utf-8", errors="replace")
            fixed, notes = _sanitize_nt_custom_csproj(text)
            if fixed != text:
                csproj.write_text(fixed, encoding="utf-8")
                logger.info("fabric.heal.csproj_sanitized: %s", notes)
            return notes
        except OSError as exc:
            logger.warning("fabric.heal.csproj_sanitize_failed: %s", exc)
            return [f"sanitize_error:{exc}"]

    pre_notes = _write_sanitized()

    nt_bin = resolve_nt_exe()
    env = os.environ.copy()
    if nt_bin is not None:
        env["NINJATRADER8_BIN"] = str(nt_bin.parent)

    # NT Custom is x64 + WPF.
    # - GenerateTargetFrameworkAttribute=false: avoid CS0579 with residual TF attrs
    # - SatelliteResourceLanguages empty: avoid generating culture resources.cs into obj
    #   that NT later may Compile into the main assembly (duplicate Assembly* attrs).
    cmd = [
        "dotnet",
        "build",
        str(csproj),
        "-c",
        "Release",
        "-p:Platform=x64",
        "-p:GenerateTargetFrameworkAttribute=false",
        "-p:GenerateAssemblyInfo=false",
        "-p:SatelliteResourceLanguages=",
        "--nologo",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(custom),
            check=False,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "status": "dotnet_missing",
            "message": "dotnet SDK not found — automatic NinjaTrader integration build skipped",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "message": "dotnet build timed out"}

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    ok = proc.returncode == 0
    # Promote build output to Custom root if needed (NT loads Custom root DLL)
    for cand in (
        custom / "bin" / "Release" / "NinjaTrader.Custom.dll",
        custom / "bin" / "x64" / "Release" / "NinjaTrader.Custom.dll",
        custom / "bin" / "Release" / "net48" / "NinjaTrader.Custom.dll",
        custom / "bin" / "Debug" / "NinjaTrader.Custom.dll",
    ):
        if cand.is_file() and ok:
            try:
                shutil.copy2(cand, custom / "NinjaTrader.Custom.dll")
            except OSError as exc:
                logger.warning("fabric.heal.copy_custom_dll_failed: %s", exc)
            break

    # CRITICAL: post-build cleanup so NinjaScript Editor / F5 is not polluted.
    post_notes = _write_sanitized()
    scrub = clean_nt_custom_obj_pollution(custom)

    return {
        "ok": ok,
        "status": "built" if ok else "build_failed",
        "returncode": proc.returncode,
        "log_tail": out[-2500:],
        "cmd": " ".join(cmd),
        "sanitize_pre": pre_notes,
        "sanitize_post": post_notes,
        "obj_scrub": scrub,
    }


def wait_for_fabric_host(
    *,
    host: str = "127.0.0.1",
    port: int = 50051,
    timeout_sec: float = 90.0,
) -> dict[str, Any]:
    from lumina_launcher.services.fabric_simhost import tcp_open

    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if tcp_open(host, port, timeout=0.6):
            # Prefer NT host status file if present
            status_path = Path(os.environ.get("APPDATA") or "") / "LUMINA" / "fabric-nt-host.json"
            state = None
            if status_path.is_file():
                try:
                    import json

                    data = json.loads(status_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        state = str(data.get("state") or "")
                except (OSError, json.JSONDecodeError):
                    pass
            return {
                "ok": True,
                "status": "listening",
                "elapsed_sec": round(time.time() - t0, 2),
                "nt_host_state": state,
            }
        time.sleep(1.0)
    return {
        "ok": False,
        "status": "timeout",
        "message": f"No Fabric host on {host}:{port} within {timeout_sec:.0f}s",
        "elapsed_sec": round(time.time() - t0, 2),
    }


def promote_staged_dlls(custom: Path, *, allow_while_nt_running: bool = False) -> list[str]:
    """Rename *.dll.new → *.dll when present.

    Code Red: never promote while NinjaTrader is running (overwrite can crash NT).
    Never promote a stub NtBridge over a product-complete bridge.
    """
    from lumina_launcher.services.fabric_deploy_integrity import verify_nt_bridge_dll

    promoted: list[str] = []
    if not custom.is_dir():
        return promoted
    if not allow_while_nt_running and is_ninjatrader_running():
        logger.info("fabric.heal.promote_skipped_nt_running custom=%s", custom)
        return promoted
    dirs = [custom]
    addons = custom / "AddOns"
    if addons.is_dir():
        dirs.append(addons)
    for dest_dir in dirs:
        for p in list(dest_dir.glob("*.dll.new")):
            # Lumina.Fabric.NtBridge.dll.new → Lumina.Fabric.NtBridge.dll
            final = dest_dir / p.name[: -len(".new")]
            # Never promote legacy dual-alias name
            if final.name.lower() == "luminant8addon.dll":
                try:
                    p.replace(dest_dir / (final.name + ".DUAL_DISABLE"))
                except OSError:
                    pass
                continue
            if final.name == "Lumina.Fabric.NtBridge.dll":
                stage_rep = verify_nt_bridge_dll(p)
                if not stage_rep.get("ok"):
                    try:
                        q = dest_dir / "Lumina.Fabric.NtBridge.dll.new.STUB_DISABLE"
                        if q.is_file():
                            q.unlink()
                        p.replace(q)
                        logger.warning(
                            "fabric.heal.quarantine_stub_staged %s reason=%s",
                            p,
                            stage_rep.get("reason"),
                        )
                    except OSError as exc:
                        logger.warning("fabric.heal.quarantine_stub_failed %s: %s", p, exc)
                    continue
                if final.is_file():
                    final_rep = verify_nt_bridge_dll(final)
                    if final_rep.get("ok") and int(final_rep.get("size") or 0) >= int(
                        stage_rep.get("size") or 0
                    ):
                        try:
                            p.unlink()
                        except OSError:
                            pass
                        continue
            try:
                if final.is_file():
                    final.unlink()
                p.replace(final)
                promoted.append(str(final))
            except OSError as exc:
                logger.warning("fabric.heal.promote_failed %s: %s", p, exc)
    return promoted


def run_fabric_heal(
    workspace_root: Path,
    config_manager: Any,
    *,
    close_nt: bool = False,  # default safe: never kill NT unless Repair passes True
    launch_ninjatrader_flag: bool = True,
    run_diagnostic: bool = True,
    allow_simhost: bool = False,
    force_redeploy: bool = True,
    wait_host_sec: float = 90.0,
) -> HealReport:
    """Full zero-IT repair / first-install pipeline.

    Never name a kw-only flag ``close_ninjatrader`` — that shadows the module
    function ``close_ninjatrader()`` and raises ``'bool' object is not callable``
    when NinjaTrader is running (Repair path).
    """
    from lumina_launcher.services.fabric_bootstrap import (
        deploy_fabric_addons,
        ensure_fabric_token_in_env,
        ninjatrader_custom_candidates,
    )
    from lumina_launcher.services.fabric_simhost import stop_simhost

    # Capture module function before any local rebinding (defensive).
    close_nt_fn = close_ninjatrader

    steps: list[HealStep] = []
    needs_user: list[dict[str, str]] = []
    root = Path(workspace_root)

    def add(step: HealStep) -> None:
        steps.append(step)
        logger.info("fabric.heal step=%s status=%s msg=%s", step.id, step.status, step.message)

    # --- 0 detect NT ---
    exe = resolve_nt_exe()
    if exe is None:
        add(
            HealStep(
                id="detect_nt",
                title="Find NinjaTrader 8",
                status="fail",
                message="NinjaTrader 8 not installed",
                user_message="Install NinjaTrader 8 first, then click Repair again.",
            )
        )
        needs_user.append(
            {
                "code": "install_nt",
                "title": "Install NinjaTrader 8",
                "body": "Lumina needs NinjaTrader 8 on this PC for market data and orders.",
                "cta": "download_nt",
            }
        )
        return HealReport(ok=False, overall="red", steps=steps, needs_user=needs_user)

    add(
        HealStep(
            id="detect_nt",
            title="Find NinjaTrader 8",
            status="pass",
            message=str(exe),
            user_message="NinjaTrader 8 found.",
        )
    )

    # --- 1 token ---
    try:
        token = ensure_fabric_token_in_env(config_manager)
        add(
            HealStep(
                id="token",
                title="Prepare connection secret",
                status="pass",
                message=f"token_len={len(token)}",
                user_message="Secure link token is ready.",
            )
        )
    except Exception as exc:
        add(
            HealStep(
                id="token",
                title="Prepare connection secret",
                status="fail",
                message=str(exc),
                user_message="Could not create connection token.",
            )
        )
        return HealReport(ok=False, overall="red", steps=steps, needs_user=needs_user)

    # --- 2 kill SimHost (never certify on SimHost alone) ---
    try:
        stop = stop_simhost(port=50051, force_port_simhosts=True)
        add(
            HealStep(
                id="clear_simhost",
                title="Clear temporary test host",
                status="pass",
                message=f"killed={stop.get('killed')}",
                user_message="Temporary test host cleared so NinjaTrader can connect.",
            )
        )
    except Exception as exc:
        add(
            HealStep(
                id="clear_simhost",
                title="Clear temporary test host",
                status="warn",
                message=str(exc),
                user_message="Could not clear temporary host (continuing).",
            )
        )

    # --- 3 close NT if needed ---
    nt_was_running = is_ninjatrader_running()
    if close_nt and nt_was_running:
        closed = close_nt_fn(force_after_sec=10.0, reason="fabric_heal_explicit_close_nt")
        if closed.get("ok"):
            add(
                HealStep(
                    id="close_nt",
                    title="Restart NinjaTrader",
                    status="pass",
                    message=str(closed.get("status")),
                    user_message="NinjaTrader was closed so bridge files can update.",
                )
            )
        else:
            add(
                HealStep(
                    id="close_nt",
                    title="Restart NinjaTrader",
                    status="fail",
                    message=str(closed.get("message") or closed),
                    user_message="Could not close NinjaTrader. Close it manually and click Repair again.",
                )
            )
            needs_user.append(
                {
                    "code": "close_nt_manual",
                    "title": "Close NinjaTrader",
                    "body": "Lumina needs NinjaTrader closed to install the bridge. Close it, then click Repair.",
                    "cta": "retry_repair",
                }
            )
            return HealReport(ok=False, overall="red", steps=steps, needs_user=needs_user)
    else:
        add(
            HealStep(
                id="close_nt",
                title="Restart NinjaTrader",
                status="skip",
                message="not_running_or_skipped" if not nt_was_running else "close_disabled_soft_heal",
                user_message=(
                    "NinjaTrader left running (soft setup — no force close)."
                    if nt_was_running
                    else "NinjaTrader was already closed."
                ),
            )
        )

    # --- 4 deploy ---
    custom = _primary_custom_dir()
    # Promote staged DLLs only when NT is not holding locks (after close_nt, or already down).
    if custom is not None and not is_ninjatrader_running():
        promote_staged_dlls(custom, allow_while_nt_running=False)

    deploy = deploy_fabric_addons(root)
    if force_redeploy and custom is not None:
        if not is_ninjatrader_running():
            promote_staged_dlls(custom, allow_while_nt_running=False)
        # Quarantine dual/stale bridge alias (never dual-load with NtBridge)
        for alias_name in ("LuminaNt8AddOn.dll",):
            stale = custom / alias_name
            if stale.is_file():
                try:
                    tag = "DUAL_DISABLE"
                    stale.replace(custom / f"{alias_name}.{tag}")
                except OSError:
                    pass

    integrity = (deploy.get("integrity") or {}).get("bridge_source") or {}
    integrity_ok = bool(integrity.get("ok")) and bool(deploy.get("deployed"))
    # Also require live destination integrity when available.
    dest_ok = True
    for dest in deploy.get("destinations") or []:
        di = dest.get("integrity") if isinstance(dest, dict) else None
        if isinstance(di, dict) and di.get("exists") and not di.get("ok"):
            dest_ok = False
            break
    if integrity_ok and dest_ok:
        add(
            HealStep(
                id="deploy",
                title="Install bridge files",
                status="pass",
                message=(
                    f"dest={deploy.get('destination')} copied={len(deploy.get('copied') or [])} "
                    f"bridge_size={integrity.get('size')} sha={str(integrity.get('sha256') or '')[:12]}"
                ),
                user_message="Bridge files installed into NinjaTrader (product integrity OK).",
            )
        )
    else:
        add(
            HealStep(
                id="deploy",
                title="Install bridge files",
                status="fail",
                message=str(
                    deploy.get("error")
                    or (integrity.get("reason") if integrity else None)
                    or deploy.get("missing")
                    or "bridge_integrity_failed"
                ),
                user_message=(
                    "Could not install a complete Fabric bridge. Rebuild with NINJATRADER8_BIN "
                    "and Repair again (stub DLL rejected)."
                ),
            )
        )
        return HealReport(
            ok=False,
            overall="red",
            steps=steps,
            needs_user=needs_user,
            report={"deploy": deploy},
        )

    # --- 5 inject + build Custom ---
    if custom is None:
        customs = ninjatrader_custom_candidates()
        custom = customs[0] if customs else None

    if custom is not None:
        inject = inject_lumina_source_into_csproj(custom)
        add(
            HealStep(
                id="inject_source",
                title="Register Lumina AddOn",
                status="pass" if inject.get("ok") else "warn",
                message=str(inject.get("status") or inject.get("message")),
                user_message="Lumina AddOn registered for NinjaTrader."
                if inject.get("ok")
                else "Could not auto-register AddOn (will still try bridge DLL).",
            )
        )
        build = build_ninjatrader_custom(custom)
        if build.get("ok"):
            add(
                HealStep(
                    id="build_custom",
                    title="Build NinjaTrader integration",
                    status="pass",
                    message="NinjaTrader.Custom built",
                    user_message="NinjaTrader integration built successfully.",
                )
            )
        else:
            add(
                HealStep(
                    id="build_custom",
                    title="Build NinjaTrader integration",
                    status="warn",
                    message=str(build.get("status")),
                    detail=(build.get("log_tail") or "")[-800:],
                    user_message=(
                        "Automatic NinjaTrader integration build did not finish. "
                        "Click Repair again after NinjaTrader has fully started once. "
                        "You do not need to open the NinjaScript editor."
                    ),
                )
            )
    else:
        add(
            HealStep(
                id="build_custom",
                title="Build NinjaTrader integration",
                status="skip",
                message="no custom dir",
                user_message="Custom folder not found yet — start NinjaTrader once, then Repair.",
            )
        )

    # --- 6 launch NT ---
    if launch_ninjatrader_flag:
        # Soft heal (close_nt=false): never spawn a second NT if one is already up.
        if is_ninjatrader_running():
            add(
                HealStep(
                    id="launch_nt",
                    title="Start NinjaTrader",
                    status="skip",
                    message="already_running",
                    user_message="NinjaTrader is already running — left open (no restart).",
                )
            )
        else:
            launched = launch_ninjatrader()
            if launched.get("ok"):
                add(
                    HealStep(
                        id="launch_nt",
                        title="Start NinjaTrader",
                        status="pass",
                        message=str(launched.get("exe")),
                        user_message="NinjaTrader is starting…",
                    )
                )
            else:
                add(
                    HealStep(
                        id="launch_nt",
                        title="Start NinjaTrader",
                        status="fail",
                        message=str(launched.get("message")),
                        user_message="Could not start NinjaTrader. Start it manually, then click Repair.",
                    )
                )
                needs_user.append(
                    {
                        "code": "launch_nt",
                        "title": "Start NinjaTrader",
                        "body": "Open NinjaTrader 8 yourself, wait until it is fully loaded, then click Repair.",
                        "cta": "retry_repair",
                    }
                )
                return HealReport(ok=False, overall="red", steps=steps, needs_user=needs_user)
    else:
        add(
            HealStep(
                id="launch_nt",
                title="Start NinjaTrader",
                status="skip",
                message="launch_disabled",
                user_message="Launch skipped.",
            )
        )

    # --- 7 wait for host ---
    wait = wait_for_fabric_host(timeout_sec=wait_host_sec)
    if wait.get("ok"):
        add(
            HealStep(
                id="wait_host",
                title="Wait for connection",
                status="pass",
                message=f"elapsed={wait.get('elapsed_sec')}s state={wait.get('nt_host_state')}",
                user_message="Connection channel is open.",
            )
        )
    else:
        # If allow_simhost, try SimHost as last resort for exec-only (still won't green historical)
        if allow_simhost:
            try:
                from lumina_launcher.services.fabric_simhost import ensure_simhost_token_aligned

                try:
                    from lumina_core.broker.ninjatrader.fabric_secret import (
                        read as fabric_secret_read,
                    )

                    token = str(fabric_secret_read(heal=True).token or "").strip()
                except Exception:
                    token = ""
                ensure_simhost_token_aligned(token=token, wait_sec=8.0)
            except Exception:
                pass
        add(
            HealStep(
                id="wait_host",
                title="Wait for connection",
                status="fail",
                message=str(wait.get("message") or wait),
                user_message=(
                    "NinjaTrader did not open the link in time. "
                    "If a Trust/security dialog appeared, click Yes, then Repair again. "
                    "Also connect your market data feed in NinjaTrader."
                ),
            )
        )
        needs_user.append(
            {
                "code": "wait_host",
                "title": "Accept trust dialog / wait for NT",
                "body": wait.get("message") or "Host not listening",
                "cta": "retry_repair",
            }
        )
        # Still run diagnostic for details if something is listening
        if not wait.get("ok"):
            # fall through only if we want diag; for user clarity return red
            if not run_diagnostic:
                return HealReport(ok=False, overall="red", steps=steps, needs_user=needs_user)

    # --- 7b live token + supervisor (always-on proof before dual-plane cert) ---
    try:
        from lumina_core.engine.engine_config import EngineConfig
        from lumina_launcher.services.fabric_link_ensure import (
            ensure_fabric_token_aligned_and_live,
        )

        eng_cfg = EngineConfig()
        ensured = ensure_fabric_token_aligned_and_live(
            config_manager=config_manager,
            engine_config=eng_cfg,
            workspace_root=root,
            mode_context="sim",
            connect_timeout_seconds=12.0,
            start_supervisor=True,
        )
        if ensured.get("ok"):
            add(
                HealStep(
                    id="live_auth",
                    title="Live Brain ↔ Fabric auth",
                    status="pass",
                    message=str(ensured.get("code") or "OK"),
                    user_message="Brain is authenticated to NinjaTrader Fabric (session live).",
                )
            )
        else:
            code = str(ensured.get("code") or "ERROR")
            needs_restart = bool(ensured.get("needs_nt_restart"))
            add(
                HealStep(
                    id="live_auth",
                    title="Live Brain ↔ Fabric auth",
                    status="fail" if code in {"AUTH_FAILED", "TOKEN_EMPTY"} else "warn",
                    message=f"{code}: {ensured.get('message') or ''}"[:400],
                    user_message=(
                        "Token mismatch or host not ready. "
                        + (
                            "Restart NinjaTrader once so the AddOn reloads the token, then Repair again."
                            if needs_restart
                            else "Start NinjaTrader (New → LUMINA host running), then Repair again."
                        )
                    ),
                )
            )
            if needs_restart:
                needs_user.append(
                    {
                        "code": "restart_nt_token",
                        "title": "Restart NinjaTrader once",
                        "body": (
                            "Lumina rewrote LUMINA_FABRIC_TOKEN to User env + fabric.json, but the "
                            "running NinjaTrader process still has the old secret. Restart NT, open "
                            "New → LUMINA, confirm Brain sessions ≥ 1, then Repair / Test connection."
                        ),
                        "cta": "retry_repair",
                    }
                )
    except Exception as exc:
        logger.warning("fabric.heal.live_auth_failed: %s", exc, exc_info=True)
        add(
            HealStep(
                id="live_auth",
                title="Live Brain ↔ Fabric auth",
                status="warn",
                message=str(exc),
                user_message="Could not prove live auth (continuing to dual-plane test).",
            )
        )

    # --- 8–9 diagnostic ---
    report_dict: dict[str, Any] | None = None
    overall = "unknown"
    certified = False
    if run_diagnostic:
        try:
            from lumina_launcher.services.fabric_connection_diagnostics import (
                run_fabric_connection_diagnostics,
            )
            from lumina_launcher.services.fabric_link_certificate import (
                clear_halt,
                write_certificate,
            )

            # Give host a moment after listen for AddOn Active
            time.sleep(2.0)
            report = run_fabric_connection_diagnostics(include_safe_mode=True, instrument="")
            report_dict = report.to_dict()
            overall = str(report.overall or "red")
            if overall == "green":
                hist = next((c for c in report.checks if c.id == "historical_bars"), None)
                write_certificate(
                    overall="green",
                    target=report.target,
                    token=_fabric_secret_token(),
                    workspace_root=root,
                    extra={
                        "historical_bars": getattr(hist, "status", None) or "pass",
                        "checks": [
                            {"id": c.id, "status": c.status}
                            for c in report.checks
                        ],
                    },
                )
                try:
                    clear_halt(workspace_root=root)
                except Exception:
                    pass
                certified = True
                add(
                    HealStep(
                        id="diagnostic",
                        title="Test connection",
                        status="pass",
                        message=report.summary,
                        user_message="Connection test passed. Ready for Genesis.",
                    )
                )
            else:
                # Map failed checks to human needs_user
                failed = [c for c in report.checks if c.status == "fail"]
                hist = next((c for c in report.checks if c.id == "historical_bars"), None)
                if hist and hist.status == "fail":
                    needs_user.append(
                        {
                            "code": "connect_data_feed",
                            "title": "Connect market data in NinjaTrader",
                            "body": (
                                "Lumina reached NinjaTrader, but market history is empty. "
                                "In NinjaTrader: connect your data feed, open a MES chart once, "
                                "then click Repair again."
                            ),
                            "cta": "retry_repair",
                        }
                    )
                add(
                    HealStep(
                        id="diagnostic",
                        title="Test connection",
                        status="fail" if overall == "red" else "warn",
                        message=report.summary,
                        detail="; ".join(f"{c.id}:{c.message}" for c in failed[:6]),
                        user_message=(
                            "Connection test did not fully pass. "
                            + (report.remediation[0] if report.remediation else "Click Repair again.")
                        ),
                    )
                )
        except Exception as exc:
            logger.exception("fabric.heal.diagnostic_failed")
            add(
                HealStep(
                    id="diagnostic",
                    title="Test connection",
                    status="fail",
                    message=str(exc),
                    user_message="Could not run connection test.",
                )
            )
            overall = "red"
    else:
        overall = "unknown"
        add(
            HealStep(
                id="diagnostic",
                title="Test connection",
                status="skip",
                message="skipped",
                user_message="Test skipped.",
            )
        )

    ok = overall == "green" and certified
    return HealReport(
        ok=ok,
        overall=overall if overall in {"green", "amber", "red"} else "red",
        steps=steps,
        needs_user=needs_user,
        report=report_dict,
        certified=certified,
    )
