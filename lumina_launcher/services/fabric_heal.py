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


# NT 8.1.8+ installer rewrites Custom.csproj to the vendor *source* template
# (ProjectReference to NinjaTrader.Core.csproj, SharpDX under ..\NinjaTrader\DirectX).
# Operator Documents\Custom cannot build that. Retarget to the installed bin DLLs.
_NT_INTERNAL_PROJECT_REFS: tuple[tuple[str, str], ...] = (
    ("NinjaTrader.Core.csproj", "NinjaTrader.Core.dll"),
    ("NinjaTrader.Gui.csproj", "NinjaTrader.Gui.dll"),
    ("Infralution.Localization.Wpf.csproj", "Infralution.Localization.Wpf.dll"),
)

# Assemblies third-party NinjaScripts commonly `using`. NT's NinjaScript
# compiler SSOT is Documents\NinjaTrader 8\Config.xml <References> — not the
# csproj. Refs must live in bin\Custom (NT ignores Program Files HintPaths
# for user scripts). Copy from NT bin if Custom lacks the DLL.
_WELL_KNOWN_NT_BIN_REFS: tuple[str, ...] = ("Newtonsoft.Json.dll",)

# netstandard Newtonsoft.Json (and similar) need the netstandard 2.0 facade
# (CS0012 Object). Copy the .NETFramework Facades DLL into Custom.
_WELL_KNOWN_FRAMEWORK_FACADES: tuple[str, ...] = ("netstandard.dll",)

_WELL_KNOWN_CONFIG_DLLS: tuple[str, ...] = _WELL_KNOWN_NT_BIN_REFS + _WELL_KNOWN_FRAMEWORK_FACADES

_PROTECTED_COMPILE_MARKERS: tuple[str, ...] = (
    "luminafabrichost",
    "luminant8addon",
    "assemblyinfo.cs",
    "ninjatrader.vendor.cs",
    "resource.designer.cs",
)


def _nt_bin_dir() -> Path | None:
    exe = resolve_nt_exe()
    return exe.parent if exe is not None else None


def _csproj_has_reference(text: str, assembly: str) -> bool:
    return f'<Reference Include="{assembly}"' in text or f'<Reference Include="{assembly},' in text


def _nt_bin_hint_reference(dll_path: Path, dll_name: str) -> str:
    assembly = dll_name[:-4] if dll_name.lower().endswith(".dll") else dll_name
    return (
        f'    <Reference Include="{assembly}">\n'
        f"      <SpecificVersion>False</SpecificVersion>\n"
        f"      <HintPath>{dll_path}</HintPath>\n"
        f"      <Private>False</Private>\n"
        f"    </Reference>\n"
    )


def _dll_targets_netstandard(path: Path) -> bool:
    try:
        return b".NETStandard,Version=v2.0" in path.read_bytes()
    except OSError:
        return False


def _find_framework_facade(dll_name: str) -> Path | None:
    pf86 = Path(os.environ.get("ProgramFiles(x86)") or r"C:\Program Files (x86)")
    windir = Path(os.environ.get("WINDIR") or r"C:\Windows")
    fx = pf86 / "Reference Assemblies" / "Microsoft" / "Framework" / ".NETFramework"
    candidates = (
        fx / "v4.8.1" / "Facades" / dll_name,
        fx / "v4.8" / "Facades" / dll_name,
        fx / "v4.7.2" / "Facades" / dll_name,
        fx / "v4.7.1" / "Facades" / dll_name,
        windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "Facades" / dll_name,
        windir / "Microsoft.NET" / "Framework" / "v4.0.30319" / "Facades" / dll_name,
    )
    for path in candidates:
        if path.is_file():
            return path
    return None


def _resolve_well_known_dll(dll_name: str, nt_bin: Path | None, custom: Path | None) -> Path | None:
    if custom is not None and (custom / dll_name).is_file():
        return custom / dll_name
    if dll_name.lower() in {n.lower() for n in _WELL_KNOWN_FRAMEWORK_FACADES}:
        # NT ignores HintPaths outside Custom; facades must be copied there first.
        return None
    if nt_bin is not None and (nt_bin / dll_name).is_file():
        return nt_bin / dll_name
    return None


def _retarget_assembly_hintpath(text: str, assembly: str, dll_path: Path) -> tuple[str, bool]:
    """Point an existing Reference HintPath at ``dll_path``. No-op if already set."""
    import re

    wanted = str(dll_path)
    if not _csproj_has_reference(text, assembly):
        return text, False
    if f"<HintPath>{wanted}</HintPath>" in text:
        return text, False
    pattern = re.compile(
        rf'(<Reference Include="{re.escape(assembly)}"[^>]*>\s*'
        rf'(?:<(?:SpecificVersion|Private)>[^<]*</(?:SpecificVersion|Private)>\s*)*'
        rf"<HintPath>)([^<]+)(</HintPath>)",
        re.IGNORECASE | re.DOTALL,
    )

    def _sub(match: re.Match[str]) -> str:
        return f"{match.group(1)}{wanted}{match.group(3)}"

    new_text, n = pattern.subn(_sub, text, count=1)
    if n:
        return new_text, True
    return text, False


def _insert_reference_itemgroup(text: str, refs: list[str]) -> str:
    block = "  <ItemGroup>\n" + "".join(refs) + "  </ItemGroup>\n"
    compile_idx = text.find("<Compile Include=")
    if compile_idx >= 0:
        ig = text.rfind("<ItemGroup>", 0, compile_idx)
        if ig >= 0:
            return text[:ig] + block + text[ig:]
        return text.replace("</Project>", block + "</Project>", 1)
    if "</Project>" in text:
        return text.replace("</Project>", block + "</Project>", 1)
    return text + "\n" + block


def _ensure_well_known_nt_bin_refs(
    text: str,
    nt_bin: Path | None,
    custom: Path | None = None,
) -> tuple[str, list[str]]:
    """Add/retarget HintPath refs for well-known assemblies (Newtonsoft.Json, …).

    Prefer the copy in ``custom`` — NT's compiler only accepts Custom-folder DLLs
    for user NinjaScripts. Program Files HintPaths work for ``dotnet build`` and
    are ignored by the NinjaScript editor.
    """
    notes: list[str] = []
    if not text:
        return text, notes
    added: list[str] = []
    for dll_name in _WELL_KNOWN_CONFIG_DLLS:
        assembly = dll_name[:-4]
        dll_path = _resolve_well_known_dll(dll_name, nt_bin, custom)
        if dll_path is None:
            notes.append(f"skipped_missing_{assembly}")
            continue
        if _csproj_has_reference(text, assembly):
            text, moved = _retarget_assembly_hintpath(text, assembly, dll_path)
            if moved:
                notes.append(f"retargeted_ref_{assembly}")
            continue
        added.append(_nt_bin_hint_reference(dll_path, dll_name))
        notes.append(f"added_ref_{assembly}")
    if added:
        text = _insert_reference_itemgroup(text, added)
    return text, notes


def _ensure_well_known_dlls_in_custom(custom: Path, nt_bin: Path | None) -> list[str]:
    """Copy well-known DLLs into Custom (NT compiler only refs this folder).

    If Custom already has a *netstandard* Newtonsoft.Json and NT bin has the
    net45 build, replace it while NT is stopped — CS0012 Object/netstandard.
    Never overwrite while NinjaTrader is running (loaded vendor DLL).
    """
    notes: list[str] = []
    nt_up = is_ninjatrader_running()
    for dll_name in _WELL_KNOWN_NT_BIN_REFS:
        dest = custom / dll_name
        src = (nt_bin / dll_name) if nt_bin is not None else None
        if dest.is_file():
            if (
                src is not None
                and src.is_file()
                and _dll_targets_netstandard(dest)
                and not _dll_targets_netstandard(src)
            ):
                if nt_up:
                    notes.append(f"skipped_replace_nt_running_{dll_name}")
                    continue
                try:
                    shutil.copy2(src, dest)
                    notes.append(f"replaced_netstandard_{dll_name}")
                except OSError as exc:
                    logger.warning("fabric.heal.replace_well_known_failed %s: %s", dest, exc)
                    notes.append(f"replace_failed_{dll_name}")
            continue
        if src is None or not src.is_file():
            notes.append(f"missing_{dll_name}")
            continue
        try:
            shutil.copy2(src, dest)
            notes.append(f"copied_{dll_name}")
        except OSError as exc:
            logger.warning("fabric.heal.copy_well_known_failed %s: %s", dest, exc)
            notes.append(f"copy_failed_{dll_name}")
    for dll_name in _WELL_KNOWN_FRAMEWORK_FACADES:
        dest = custom / dll_name
        if dest.is_file():
            continue
        src = _find_framework_facade(dll_name)
        if src is None:
            notes.append(f"missing_facade_{dll_name}")
            continue
        try:
            shutil.copy2(src, dest)
            notes.append(f"copied_facade_{dll_name}")
        except OSError as exc:
            logger.warning("fabric.heal.copy_facade_failed %s: %s", dest, exc)
            notes.append(f"copy_failed_{dll_name}")
    return notes


def _ninjascript_config_path(custom: Path) -> Path:
    # Documents\NinjaTrader 8\bin\Custom → Documents\NinjaTrader 8\Config.xml
    return custom.parent.parent / "Config.xml"


def _config_reference_token(custom: Path, dll_name: str) -> str:
    """Match NT's Vendor token: *MyDocuments*\\NinjaTrader 8\\bin\\Custom\\Name.dll."""
    if custom.name.lower() == "custom" and custom.parent.name.lower() == "bin":
        nt8 = custom.parent.parent.name
        return f"*MyDocuments*\\{nt8}\\bin\\Custom\\{dll_name}"
    return str(custom / dll_name)


def ensure_ninjascript_config_references(custom: Path) -> dict[str, Any]:
    """Add well-known Custom DLLs to Config.xml <References> (NT compiler SSOT).

    NinjaTrader support: editing the csproj alone is ignored; the editor compiles
    from Config.xml. Never writes while NT is running (NT overwrites on exit).
    Never kills NinjaTrader.
    """
    if is_ninjatrader_running():
        return {"ok": True, "status": "skipped_nt_running", "changed": False}
    config = _ninjascript_config_path(custom)
    if not config.is_file():
        return {"ok": True, "status": "no_config", "changed": False, "path": str(config)}
    try:
        text = config.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return {"ok": False, "status": "read_failed", "changed": False, "message": str(exc)}

    start = text.find("<References>")
    end = text.find("</References>", start) if start >= 0 else -1
    if start < 0 or end < 0:
        return {"ok": True, "status": "no_references_node", "changed": False, "path": str(config)}
    section = text[start:end]
    added: list[str] = []
    nl = "\r\n" if "\r\n" in text else "\n"
    insert_xml = ""
    for dll_name in _WELL_KNOWN_CONFIG_DLLS:
        if dll_name.lower() in section.lower():
            continue
        if not (custom / dll_name).is_file():
            continue
        token = _config_reference_token(custom, dll_name)
        insert_xml += f"      <string>{token}</string>{nl}"
        added.append(dll_name)
    if not added:
        return {"ok": True, "status": "already_present", "changed": False, "path": str(config)}
    close = text.rfind("</ArrayOfString>", start, end)
    if close < 0:
        return {"ok": False, "status": "no_arrayofstring", "changed": False, "path": str(config)}
    text = text[:close] + insert_xml + text[close:]

    backup = config.with_suffix(".xml.bak_lumina_heal")
    try:
        if not backup.is_file():
            shutil.copy2(config, backup)
        config.write_text(text, encoding="utf-8-sig")
    except OSError as exc:
        return {"ok": False, "status": "write_failed", "changed": False, "message": str(exc)}
    logger.info("fabric.heal.config_references_added: %s", added)
    return {
        "ok": True,
        "status": "added",
        "changed": True,
        "path": str(config),
        "added": added,
    }


def _is_protected_compile(include_or_path: str) -> bool:
    name = include_or_path.replace("/", "\\").lower()
    base = Path(name).name
    if base.startswith("%40") or base.startswith("@"):
        return True
    return any(marker in name for marker in _PROTECTED_COMPILE_MARKERS)


def _failing_cs_basenames(build_log: str) -> list[str]:
    import re

    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"([^\\/:\s]+\.cs)\(\d+,\d+\):\s+error\s+CS\d+", build_log, re.I):
        base = match.group(1)
        key = base.lower()
        if key not in seen:
            seen.add(key)
            found.append(base)
    return found


def isolate_failing_third_party_scripts(csproj_text: str, build_log: str) -> tuple[str, list[str]]:
    """Drop Compile Include for non-Lumina scripts that failed the Custom build.

    NT compiles every Custom NinjaScript into one NinjaTrader.Custom.dll.
    A third-party CS0246 restores the previous Custom.dll and drops LuminaFabricHost.
    Never isolate Lumina host sources or NT stock ``@`` scripts.
    """
    import re

    isolated: list[str] = []
    text = csproj_text
    for base in _failing_cs_basenames(build_log):
        if _is_protected_compile(base):
            continue
        pattern = re.compile(
            rf'^\s*<Compile\s+Include="[^"]*{re.escape(base)}"[^>]*/?>\s*\r?\n',
            re.MULTILINE | re.IGNORECASE,
        )
        new_text, n = pattern.subn("", text)
        if n:
            text = new_text
            isolated.append(base)
    return text, isolated


def _retarget_nt_custom_csproj(text: str, nt_bin: Path | None) -> tuple[str, list[str]]:
    """Rewrite NT installer source-template refs to installed NinjaTrader.Core.dll.

    Fail-closed: only rewrite when the target DLL exists in ``nt_bin``.
    """
    import re

    notes: list[str] = []
    if not text or nt_bin is None or not nt_bin.is_dir():
        return text, notes

    def _hint(dll_name: str) -> str:
        hint = str(nt_bin / dll_name)
        return (
            f'    <Reference Include="{dll_name[:-4]}">\n'
            f"      <SpecificVersion>False</SpecificVersion>\n"
            f"      <HintPath>{hint}</HintPath>\n"
            f"      <Private>False</Private>\n"
            f"    </Reference>\n"
        )

    added_refs: list[str] = []
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
    removed_needles: set[str] = set()
    for line in lines:
        drop = False
        for needle, dll_name in _NT_INTERNAL_PROJECT_REFS:
            if "ProjectReference" in line and needle.lower() in line.lower():
                drop = True
                if needle not in removed_needles:
                    removed_needles.add(needle)
                    notes.append(f"removed_projectref_{dll_name[:-4]}")
                    already = f'<Reference Include="{dll_name[:-4]}"' in text and dll_name in text
                    if not already and (nt_bin / dll_name).is_file():
                        added_refs.append(_hint(dll_name))
                break
        if not drop:
            kept.append(line)
    if removed_needles:
        text = "".join(kept)

    # 8.1.8 installer SharpDX path lives in the NT source tree, not Documents\Custom.
    sharp_pat = re.compile(
        r"<HintPath>\.\.[\\/]NinjaTrader[\\/]DirectX[\\/]([^<]+)</HintPath>",
        re.IGNORECASE,
    )

    def _sharp_sub(match: re.Match[str]) -> str:
        name = match.group(1).strip()
        return f"<HintPath>{nt_bin / name}</HintPath>"

    text, n_sharp = sharp_pat.subn(_sharp_sub, text)
    if n_sharp:
        notes.append(f"retargeted_{n_sharp}_sharpdx_hintpaths")

    if added_refs:
        block = "  <ItemGroup>\n" + "".join(added_refs) + "  </ItemGroup>\n"
        compile_idx = text.find("<Compile Include=")
        if compile_idx >= 0:
            ig = text.rfind("<ItemGroup>", 0, compile_idx)
            if ig >= 0:
                text = text[:ig] + block + text[ig:]
            else:
                text = text.replace("</Project>", block + "</Project>", 1)
        elif "</Project>" in text:
            text = text.replace("</Project>", block + "</Project>", 1)
        notes.append(f"added_{len(added_refs)}_nt_bin_references")

    return text, notes


def _sanitize_nt_custom_csproj(
    text: str,
    nt_bin: Path | None = None,
    custom: Path | None = None,
) -> tuple[str, list[str]]:
    """Strip obj/ junk Compile entries that break NinjaScript (CS0579/CS2001).

    External ``dotnet build`` of NinjaTrader.Custom generates under ``obj\\``:
    - ``*.AssemblyAttributes.cs``
    - satellite ``*.resources.cs`` (per culture) with full [assembly:] attributes

    If those land in the main project Compile list (NT auto-add or stale csproj),
    they collide with root ``AssemblyInfo.cs`` → mass CS0579 in the editor.
    Never compile anything under ``obj\\`` into NinjaTrader.Custom.

    Also retarget NT 8.1.8+ installer ProjectReferences onto the installed bin
    and add well-known NT-bin refs (Newtonsoft.Json) so third-party NinjaScripts
    compile without operator F5.
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

    retargeted, retarget_notes = _retarget_nt_custom_csproj(text, nt_bin)
    if retarget_notes:
        text = retargeted
        notes.extend(retarget_notes)

    ensured, ensure_notes = _ensure_well_known_nt_bin_refs(text, nt_bin, custom)
    if ensure_notes:
        text = ensured
        notes.extend(ensure_notes)

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

    nt_bin = _nt_bin_dir()
    dll_notes = _ensure_well_known_dlls_in_custom(custom, nt_bin)
    original = csproj.read_text(encoding="utf-8", errors="replace")
    text, sanitize_notes = _sanitize_nt_custom_csproj(original, nt_bin, custom)
    sanitize_notes = list(dll_notes) + list(sanitize_notes)
    marker = "LuminaFabricHost"
    include_line = '    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />\n'
    already = marker in text
    if not already:
        insert = include_line
        if "</ItemGroup>" in text:
            idx = text.find("<Compile Include=")
            if idx >= 0:
                line_start = text.rfind("\n", 0, idx) + 1
                text = text[:line_start] + insert + text[line_start:]
            else:
                text = text.replace("</Project>", f"  <ItemGroup>\n{insert}  </ItemGroup>\n</Project>", 1)
        else:
            text = text.replace("</Project>", f"  <ItemGroup>\n{insert}  </ItemGroup>\n</Project>", 1)

    config = ensure_ninjascript_config_references(custom)
    csproj_changed = text != original

    if not csproj_changed:
        status = "already_present"
        if config.get("changed"):
            status = "already_present+config"
        return {
            "ok": True,
            "status": status,
            "path": str(csproj),
            "sanitize": sanitize_notes,
            "config": config,
        }

    backup = csproj.with_suffix(".csproj.bak_lumina_heal")
    try:
        if not backup.is_file():
            shutil.copy2(csproj, backup)
        csproj.write_text(text, encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "status": "write_failed", "message": str(exc), "config": config}
    status = "already_present" if already else "injected"
    if sanitize_notes:
        status = f"{status}+sanitized"
    if config.get("changed"):
        status = f"{status}+config"
    return {
        "ok": True,
        "status": status,
        "path": str(csproj),
        "sanitize": sanitize_notes,
        "config": config,
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
            fixed, notes = _sanitize_nt_custom_csproj(text, _nt_bin_dir(), custom)
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
    def _run_build() -> tuple[int, str]:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(custom),
            check=False,
        )
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        return int(proc.returncode), log

    try:
        rc, out = _run_build()
    except FileNotFoundError:
        return {
            "ok": False,
            "status": "dotnet_missing",
            "message": "dotnet SDK not found — automatic NinjaTrader integration build skipped",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "message": "dotnet build timed out"}

    isolated: list[str] = []
    if rc != 0:
        try:
            raw = csproj.read_text(encoding="utf-8", errors="replace")
            new_text, isolated = isolate_failing_third_party_scripts(raw, out)
            if isolated and new_text != raw:
                csproj.write_text(new_text, encoding="utf-8")
                logger.warning("fabric.heal.isolated_third_party: %s", isolated)
                rc, out = _run_build()
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("fabric.heal.isolate_retry_failed: %s", exc)

    ok = rc == 0
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

    status = "built" if ok else "build_failed"
    if ok and isolated:
        status = "built_isolated_third_party"
    return {
        "ok": ok,
        "status": status,
        "returncode": rc,
        "log_tail": out[-2500:],
        "cmd": " ".join(cmd),
        "sanitize_pre": pre_notes,
        "sanitize_post": post_notes,
        "obj_scrub": scrub,
        "isolated": isolated,
    }


def ensure_custom_compile_ready(*, build_if_nt_stopped: bool = True) -> dict[str, Any]:
    """Zero-IT: keep Custom.csproj compilable after the NT installer rewrites it.

    Injects LuminaFabricHost, retargets installer ProjectReferences, adds
    well-known NT-bin refs (Newtonsoft.Json). Rebuilds Custom.dll only when
    NinjaTrader is **not** running (DLL lock / Code Red). Never kills NT.
    """
    custom = _primary_custom_dir()
    nt_running = is_ninjatrader_running()
    result: dict[str, Any] = {
        "ok": False,
        "custom": str(custom) if custom is not None else None,
        "nt_running": nt_running,
        "csproj_changed": False,
        "built": False,
        "inject": None,
        "build": None,
    }
    if custom is None:
        result["build"] = {"status": "skipped_no_custom"}
        return result

    inject = inject_lumina_source_into_csproj(custom)
    result["inject"] = inject
    status = str(inject.get("status") or "")
    result["csproj_changed"] = bool(inject.get("ok")) and (
        "sanitized" in status or status.startswith("injected")
    )
    if not inject.get("ok"):
        result["build"] = {"status": "skipped_inject_failed"}
        return result

    dll = custom / "NinjaTrader.Custom.dll"
    if nt_running:
        result["ok"] = True
        result["build"] = {"status": "skipped_nt_running"}
        return result

    if not build_if_nt_stopped:
        result["ok"] = True
        result["build"] = {"status": "skipped_build_disabled"}
        return result

    if dll.is_file() and not result["csproj_changed"]:
        result["ok"] = True
        result["build"] = {"status": "skipped_already_built"}
        return result

    build = build_ninjatrader_custom(custom)
    result["build"] = build
    result["built"] = bool(build.get("ok"))
    result["ok"] = bool(build.get("ok"))
    return result


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
            isolated = [str(x) for x in (build.get("isolated") or []) if str(x).strip()]
            add(
                HealStep(
                    id="build_custom",
                    title="Build NinjaTrader integration",
                    status="pass",
                    message=(
                        f"NinjaTrader.Custom built isolated={isolated}"
                        if isolated
                        else "NinjaTrader.Custom built"
                    ),
                    user_message=(
                        "NinjaTrader integration built. A third-party NinjaScript could not "
                        "compile and was skipped so Lumina still works."
                        if isolated
                        else "NinjaTrader integration built successfully."
                    ),
                    detail=", ".join(isolated) if isolated else None,
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
            report = run_fabric_connection_diagnostics(include_safe_mode=False, instrument="", allow_live_order_probe=False)
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
