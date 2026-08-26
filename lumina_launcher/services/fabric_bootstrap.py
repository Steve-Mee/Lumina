"""Zero-touch Fabric bootstrap: token, fabric.json, AddOn DLL deploy."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from lumina_launcher.services.fabric_deploy_integrity import (
    NT_BRIDGE_MIN_BYTES,
    collect_bridge_candidates,
    dual_tree_bridge_drift,
    pick_best_nt_bridge,
    verify_fabric_core_dll,
    verify_nt_bridge_dll,
)
from lumina_launcher.services.setup_persist import (
    apply_fabric_token_side_effects,
    generate_fabric_token,
    write_fabric_json_defaults,
)

logger = logging.getLogger(__name__)

# Relative to workspace; build/release artifacts preferred.
# Prefer Release net48 (full NT types) over deploy/AddOns packaging.
FABRIC_DEPLOY_CANDIDATES = (
    Path("integrations/ninjatrader8/LuminaNt8AddOn/bin/Release/net48"),
    Path("integrations/ninjatrader8/deploy/AddOns"),
    Path("tauri-app/src-tauri/resources/fabric"),
)

FABRIC_DLL_NAMES = (
    # Single bridge assembly name only — dual-load of LuminaNt8AddOn.dll + NtBridge crashes/thrash risk.
    "Lumina.Fabric.NtBridge.dll",
    "Lumina.Execution.Fabric.dll",
    "Google.Protobuf.dll",
    "Grpc.Core.dll",
    "Grpc.Core.Api.dll",
    "grpc_csharp_ext.x64.dll",
    "grpc_csharp_ext.x86.dll",
    "System.Memory.dll",
    "System.Buffers.dll",
    "System.Runtime.CompilerServices.Unsafe.dll",
    "System.Threading.Tasks.Extensions.dll",
    "System.Numerics.Vectors.dll",
    "System.ValueTuple.dll",
    "Microsoft.Bcl.AsyncInterfaces.dll",
    "System.Text.Json.dll",
    "System.Text.Encodings.Web.dll",
)

# Never deploy these as active vendor assemblies when NtBridge is present.
_LEGACY_BRIDGE_ALIASES = ("LuminaNt8AddOn.dll",)


def _windows_my_documents() -> Path | None:
    """Resolve real My Documents (OneDrive-aware on Windows)."""
    if os.name != "nt":
        return None
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(260)
        # CSIDL_PERSONAL = 5
        if int(ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)) == 0:
            p = Path(str(buf.value or "").strip())
            if p.is_dir():
                return p
    except Exception:
        logger.debug("SHGetFolderPathW failed", exc_info=True)
    return None


def ninjatrader_custom_candidates() -> list[Path]:
    """Possible NT8 bin\\Custom roots (Documents vs OneDrive Documenten)."""
    home = Path.home()
    bases: list[Path] = []
    my_docs = _windows_my_documents()
    if my_docs is not None:
        bases.append(my_docs)
    bases.extend(
        [
            home / "Documents",
            home / "OneDrive" / "Documenten",
            home / "OneDrive" / "Documents",
        ]
    )
    out: list[Path] = []
    seen: set[str] = set()
    for base in bases:
        custom = (base / "NinjaTrader 8" / "bin" / "Custom").resolve()
        key = str(custom).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(custom)
    return out


def ninjatrader_documents_addons() -> Path:
    """Primary AddOns folder (My Documents — OneDrive-aware)."""
    customs = ninjatrader_custom_candidates()
    for custom in customs:
        if custom.is_dir() or (custom.parent.parent / "log").is_dir():
            return custom / "AddOns"
    home = Path.home()
    return home / "Documents" / "NinjaTrader 8" / "bin" / "Custom" / "AddOns"


def resolve_fabric_source_dir(workspace_root: Path) -> Path | None:
    """Resolve directory that holds a *product-complete* NtBridge when possible."""
    best_bridge = pick_best_nt_bridge(collect_bridge_candidates(workspace_root))
    if best_bridge is not None:
        return best_bridge.parent
    for rel in FABRIC_DEPLOY_CANDIDATES:
        candidate = workspace_root / rel
        if candidate.is_dir() and (
            (candidate / "Lumina.Fabric.NtBridge.dll").is_file()
            or (candidate / "LuminaNt8AddOn.dll").is_file()
        ):
            return candidate
        # SimHost folder may have Fabric.dll without AddOn — still useful partial
        if candidate.is_dir() and (candidate / "Lumina.Execution.Fabric.dll").is_file():
            return candidate
    return None


def deploy_fabric_addons(workspace_root: Path) -> dict[str, Any]:
    """Deploy Fabric DLLs where NT actually loads 3rd-party assemblies.

    NinjaTrader loads vendor/3rd-party AddOns from ``bin\\Custom\\`` (root),
    same pattern as CrossTrade_AddOn_*.dll — NOT only from ``AddOns\\``.
    Also copies into ``AddOns\\`` for completeness.

    My Documents may be OneDrive (``...\\OneDrive\\Documenten``); a plain
    ``~/Documents`` tree is often a stale non-redirected folder.
    """
    source = resolve_fabric_source_dir(workspace_root)
    customs = [c for c in ninjatrader_custom_candidates() if c.parent.parent.exists() or c.exists()]
    if not customs:
        customs = [ninjatrader_documents_addons().parent]

    result: dict[str, Any] = {
        "deployed": False,
        "source": str(source) if source else None,
        "destination": str(customs[0] if customs else ""),
        "destinations": [],
        "copied": [],
        "missing": [],
        "error": None,
        "integrity": {},
        "drift": {},
    }
    if source is None:
        result["error"] = "No Fabric build artifacts found under integrations/ninjatrader8"
        result["missing"] = list(FABRIC_DLL_NAMES)
        return result

    # Fail-closed: never deploy a stub/standalone NtBridge as product.
    best_bridge = pick_best_nt_bridge(
        [
            source / "Lumina.Fabric.NtBridge.dll",
            source / "LuminaNt8AddOn.dll",
            *collect_bridge_candidates(workspace_root),
        ]
    )
    if best_bridge is None:
        result["error"] = (
            "No product-complete Lumina.Fabric.NtBridge.dll found "
            f"(need ≥{NT_BRIDGE_MIN_BYTES} bytes + NtAccountOrderGateway/"
            "NtHistoricalDataProvider/NtLiveMarketDataProvider). "
            "Build with NINJATRADER8_BIN set."
        )
        result["integrity"] = {
            "bridge": verify_nt_bridge_dll(source / "Lumina.Fabric.NtBridge.dll"),
        }
        return result
    result["source"] = str(best_bridge.parent)
    result["integrity"]["bridge_source"] = verify_nt_bridge_dll(best_bridge)
    source = best_bridge.parent

    def _install_score(custom: Path) -> tuple[int, float]:
        """Prefer live OneDrive install: CrossTrade present + newest log wins."""
        score = 0
        mtime = 0.0
        if (custom / "NinjaTrader.Custom.dll").is_file():
            score += 1
        if any(custom.glob("CrossTrade_AddOn*.dll")):
            score += 10  # strong signal of the operator's real NT tree
        log_dir = custom.parent.parent / "log"
        if log_dir.is_dir():
            for logf in log_dir.glob("log.*.txt"):
                try:
                    mtime = max(mtime, float(logf.stat().st_mtime))
                except OSError:
                    pass
            if mtime > 0:
                score += 2
        return score, mtime

    ranked = sorted(customs, key=_install_score, reverse=True)
    # Deploy to best match + any other scored install (skip empty placeholders).
    targets = [c for c in ranked if _install_score(c)[0] > 0] or ranked[:1]
    primary = targets[0] if targets else customs[0]
    result["destination"] = str(primary)

    any_ok = False
    for custom in targets:
        addons = custom / "AddOns"
        try:
            custom.mkdir(parents=True, exist_ok=True)
            addons.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Fabric deploy cannot create %s: %s", custom, exc)
            continue

        dest_info: dict[str, Any] = {"custom": str(custom), "copied": [], "missing": [], "quarantined": []}

        # Code Red: never dual-load bridge under two names (NT vendor log showed both).
        for alias in _LEGACY_BRIDGE_ALIASES:
            for dest_dir in (custom, addons):
                legacy_path = dest_dir / alias
                if not legacy_path.is_file():
                    continue
                try:
                    if legacy_path.stat().st_size < 20_000 or (custom / "Lumina.Fabric.NtBridge.dll").is_file():
                        q = dest_dir / f"{alias}.DUAL_DISABLE"
                        try:
                            if q.is_file():
                                q.unlink()
                        except OSError:
                            pass
                        legacy_path.replace(q)
                        dest_info["quarantined"].append(str(q.name))
                        logger.info("Fabric deploy quarantined dual bridge alias %s", legacy_path)
                except OSError as exc:
                    logger.warning("Fabric deploy could not quarantine %s: %s", legacy_path, exc)

        # If NT is running, never overwrite loaded DLLs in-place (can crash NT process).
        nt_running = False
        try:
            from lumina_launcher.services.fabric_simhost import is_ninjatrader_running

            nt_running = bool(is_ninjatrader_running())
        except Exception:
            nt_running = False

        def _promote_or_quarantine_staged(dest_dir: Path) -> None:
            """Promote *.dll.new when safe; never promote stub NtBridge over product."""
            if nt_running:
                return
            for stage_path in list(dest_dir.glob("*.dll.new")):
                final_name = stage_path.name[: -len(".new")]
                final_path = dest_dir / final_name
                if final_name == "Lumina.Fabric.NtBridge.dll":
                    stage_rep = verify_nt_bridge_dll(stage_path)
                    if not stage_rep.get("ok"):
                        q = dest_dir / "Lumina.Fabric.NtBridge.dll.new.STUB_DISABLE"
                        try:
                            if q.is_file():
                                q.unlink()
                            stage_path.replace(q)
                            dest_info["quarantined"].append(q.name)
                            logger.warning(
                                "Fabric deploy quarantined stub staged bridge %s reason=%s",
                                stage_path,
                                stage_rep.get("reason"),
                            )
                        except OSError as exc:
                            logger.warning("Could not quarantine staged stub: %s", exc)
                        continue
                    if final_path.is_file():
                        final_rep = verify_nt_bridge_dll(final_path)
                        if final_rep.get("ok") and int(final_rep.get("size") or 0) >= int(
                            stage_rep.get("size") or 0
                        ):
                            try:
                                stage_path.unlink()
                            except OSError:
                                pass
                            continue
                try:
                    if final_path.is_file():
                        final_path.unlink()
                    stage_path.replace(final_path)
                    dest_info["copied"].append(f"promoted:{final_name}")
                except OSError as exc:
                    logger.warning("Fabric promote failed %s: %s", stage_path, exc)

        # Promote any prior staged files BEFORE writing a fresh product copy so a
        # leftover stub .new cannot overwrite a good in-place deploy later.
        _promote_or_quarantine_staged(custom)
        _promote_or_quarantine_staged(addons)

        for name in FABRIC_DLL_NAMES:
            if name == "Lumina.Fabric.NtBridge.dll":
                src = best_bridge
            else:
                src = _resolve_dll_source(workspace_root, source, name)
            if src is None:
                dest_info["missing"].append(name)
                if name not in result["missing"]:
                    result["missing"].append(name)
                continue
            for dest_dir in (custom, addons):
                dest_path = dest_dir / name
                stage_path = dest_dir / (name + ".new")
                try:
                    if nt_running and name.endswith(".dll"):
                        # Stage only — next Repair/boot promotes after clean exit.
                        shutil.copy2(src, stage_path)
                        tag = f"{dest_dir.name}/{name}.new" if dest_dir == addons else f"Custom/{name}.new"
                    else:
                        shutil.copy2(src, dest_path)
                        tag = f"{dest_dir.name}/{name}" if dest_dir == addons else f"Custom/{name}"
                    dest_info["copied"].append(tag)
                    if tag not in result["copied"]:
                        result["copied"].append(tag)
                    any_ok = True
                except OSError as exc:
                    try:
                        shutil.copy2(src, stage_path)
                        tag = f"{dest_dir.name}/{name}.new" if dest_dir == addons else f"Custom/{name}.new"
                        dest_info["copied"].append(tag)
                        if tag not in result["copied"]:
                            result["copied"].append(tag)
                        any_ok = True
                        logger.info("Fabric deploy staged locked %s as %s", name, stage_path.name)
                    except OSError as stage_exc:
                        logger.warning(
                            "Fabric deploy copy failed %s -> %s: %s (stage: %s)",
                            name,
                            dest_dir,
                            exc,
                            stage_exc,
                        )
                        dest_info["missing"].append(name)

        # Promote again after copy (handles NT-was-running stages from this pass).
        _promote_or_quarantine_staged(custom)
        _promote_or_quarantine_staged(addons)

        # Post-copy integrity on primary Custom path (or staged .new when NT running).
        bridge_dest = custom / "Lumina.Fabric.NtBridge.dll"
        bridge_stage = custom / "Lumina.Fabric.NtBridge.dll.new"
        check_path = bridge_dest if bridge_dest.is_file() else bridge_stage
        dest_integrity = verify_nt_bridge_dll(check_path)
        dest_info["integrity"] = dest_integrity
        if not dest_integrity.get("ok") and not nt_running:
            # Last chance: force product bridge copy, then re-verify.
            try:
                shutil.copy2(best_bridge, bridge_dest)
                shutil.copy2(best_bridge, addons / "Lumina.Fabric.NtBridge.dll")
                dest_integrity = verify_nt_bridge_dll(bridge_dest)
                dest_info["integrity"] = dest_integrity
            except OSError as exc:
                logger.warning("Force bridge copy failed: %s", exc)
        if not dest_integrity.get("ok") and not nt_running:
            # Quarantine stub so NT cannot load a hollow bridge.
            if bridge_dest.is_file():
                try:
                    q = custom / "Lumina.Fabric.NtBridge.dll.STUB_DISABLE"
                    try:
                        if q.is_file():
                            q.unlink()
                    except OSError:
                        pass
                    bridge_dest.replace(q)
                    dest_info["quarantined"].append(q.name)
                    logger.error(
                        "Fabric deploy quarantined stub NtBridge at %s reason=%s",
                        bridge_dest,
                        dest_integrity.get("reason"),
                    )
                except OSError as exc:
                    logger.warning("Could not quarantine stub NtBridge: %s", exc)
            dest_info["error"] = f"bridge_integrity_failed:{dest_integrity.get('reason')}"
            result["error"] = dest_info["error"]
            any_ok = False
        elif not dest_integrity.get("ok") and nt_running:
            dest_info["error"] = f"bridge_integrity_staged_or_failed:{dest_integrity.get('reason')}"
            result["error"] = dest_info["error"]
            any_ok = False

        # CrossTrade-style stub so NinjaScript Editor stays happy if present
        stub_src = workspace_root / "integrations/ninjatrader8/deploy/LuminaNt8AddOn.stub.cs"
        stub_dst = custom / "LuminaNt8AddOn.cs"
        if stub_src.is_file():
            try:
                shutil.copy2(stub_src, stub_dst)
                dest_info["copied"].append("Custom/LuminaNt8AddOn.cs")
            except OSError:
                pass

        # Authoritative source AddOn (heal/build injects into NinjaTrader.Custom — zero-IT)
        source_addon = (
            workspace_root / "integrations/ninjatrader8/deploy/AddOns/@LuminaFabricHost.cs"
        )
        if source_addon.is_file():
            try:
                shutil.copy2(source_addon, addons / "@LuminaFabricHost.cs")
                dest_info["copied"].append("AddOns/@LuminaFabricHost.cs")
            except OSError:
                pass

        result["destinations"].append(dest_info)

    # Drift report across all Custom trees (Documents vs OneDrive).
    try:
        result["drift"] = dual_tree_bridge_drift(
            [c for c in ninjatrader_custom_candidates() if c.is_dir()]
        )
        if result["drift"].get("any_stub"):
            logger.warning(
                "Fabric dual-tree has stub/incomplete NtBridge — Repair required on all trees"
            )
    except Exception:
        logger.debug("fabric.deploy.drift_check_failed", exc_info=True)

    result["deployed"] = any_ok and (
        any("Lumina.Fabric.NtBridge.dll" in c for c in result["copied"])
        and result.get("error") is None
    )
    if not result["deployed"] and result["error"] is None:
        result["error"] = "No DLLs copied to any NinjaTrader Custom folder"
    # Surface Fabric core integrity for observability.
    try:
        core_src = _resolve_dll_source(
            workspace_root, source, "Lumina.Execution.Fabric.dll"
        )
        if core_src is not None:
            result["integrity"]["fabric_core"] = verify_fabric_core_dll(core_src)
    except Exception:
        logger.debug("fabric.deploy.core_integrity_failed", exc_info=True)

    # Operator timeline: durable deploy manifest (hash + destination).
    try:
        _write_deploy_manifest(result)
    except Exception:
        logger.debug("fabric.deploy.manifest_write_failed", exc_info=True)
    return result


def _write_deploy_manifest(deploy_result: dict[str, Any]) -> Path | None:
    """Write %APPDATA%/LUMINA/fabric-deploy-manifest.json for operator SSOT."""
    import json
    import time
    from datetime import datetime, timezone

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    out_dir = base / "LUMINA"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "fabric-deploy-manifest.json"
    bridge = (deploy_result.get("integrity") or {}).get("bridge_source") or {}
    payload = {
        "schema": "fabric_deploy_manifest_v1",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "epoch": time.time(),
        "deployed": bool(deploy_result.get("deployed")),
        "source": deploy_result.get("source"),
        "destination": deploy_result.get("destination"),
        "error": deploy_result.get("error"),
        "bridge_sha256": bridge.get("sha256"),
        "bridge_size": bridge.get("size"),
        "bridge_ok": bridge.get("ok"),
        "drift": deploy_result.get("drift") or {},
        "copied_count": len(deploy_result.get("copied") or []),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _resolve_dll_source(workspace_root: Path, source: Path, name: str) -> Path | None:
    candidates = [
        source / name,
        workspace_root
        / "integrations/ninjatrader8/LuminaNt8AddOn/bin/Release/net48"
        / name,
        workspace_root
        / "integrations/ninjatrader8/Lumina.Execution.Fabric/bin/Release/net48"
        / name,
        workspace_root / "integrations/ninjatrader8/deploy/AddOns" / name,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def ensure_fabric_token_in_env(config_manager: Any) -> str:
    """Return token, generating + writing if absent.

    Dual-writes process env, User env, and fabric.json AuthToken via
    ``apply_fabric_token_side_effects`` (do not call bare write_fabric_json_defaults
    afterward — that historically stripped AuthToken).
    """
    env_values = config_manager.parse_env_file()
    token = str(env_values.get("LUMINA_FABRIC_TOKEN") or os.getenv("LUMINA_FABRIC_TOKEN") or "").strip()
    if not token:
        token = generate_fabric_token()
        config_manager.write_env_file({"LUMINA_FABRIC_TOKEN": token})
    os.environ["LUMINA_FABRIC_TOKEN"] = token
    apply_fabric_token_side_effects(token)
    return token


def run_fabric_bootstrap(workspace_root: Path, config_manager: Any) -> dict[str, Any]:
    """Idempotent bootstrap for Operator Vault mount / seal."""
    token = ensure_fabric_token_in_env(config_manager)
    # Keep AuthToken in fabric.json (ensure already dual-wrote it).
    fabric_json = write_fabric_json_defaults(auth_token=token)
    deploy = deploy_fabric_addons(workspace_root)
    simhost: dict[str, Any] = {"ok": False, "status": "skipped"}
    try:
        from lumina_launcher.services.fabric_simhost import ensure_simhost_token_aligned
        from lumina_launcher.services.setup_persist_fabric import fabric_json_path
        import json

        host, port, account = "127.0.0.1", 50051, "Sim101"
        path = fabric_json_path()
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    host = str(data.get("BindHost") or host)
                    port = int(data.get("BindPort") or port)
                    account = str(data.get("AccountName") or account)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        simhost = ensure_simhost_token_aligned(
            host=host,
            port=port,
            token=token,
            account=account,
            workspace_root=workspace_root,
            wait_sec=8.0,
        )
    except Exception as exc:
        logger.warning("fabric.bootstrap.simhost_failed: %s", exc)
        simhost = {"ok": False, "status": "error", "message": str(exc)}
    return {
        "token_ready": bool(token),
        "token_length": len(token),
        "fabric_json": str(fabric_json),
        "deploy": deploy,
        "gateway_mode": "nt",
        "simhost": simhost,
    }
