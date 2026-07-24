"""Zero-touch Fabric bootstrap: token, fabric.json, AddOn DLL deploy."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from lumina_launcher.services.setup_persist import (
    apply_fabric_token_side_effects,
    generate_fabric_token,
    write_fabric_json_defaults,
)

logger = logging.getLogger(__name__)

# Relative to workspace; build/release artifacts preferred.
FABRIC_DEPLOY_CANDIDATES = (
    Path("integrations/ninjatrader8/deploy/AddOns"),
    Path("integrations/ninjatrader8/LuminaNt8AddOn/bin/Release/net48"),
    Path("tauri-app/src-tauri/resources/fabric"),
)

FABRIC_DLL_NAMES = (
    "LuminaNt8AddOn.dll",
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


def ninjatrader_documents_addons() -> Path:
    home = Path.home()
    return home / "Documents" / "NinjaTrader 8" / "bin" / "Custom" / "AddOns"


def resolve_fabric_source_dir(workspace_root: Path) -> Path | None:
    for rel in FABRIC_DEPLOY_CANDIDATES:
        candidate = workspace_root / rel
        if candidate.is_dir() and (candidate / "LuminaNt8AddOn.dll").is_file():
            return candidate
        # SimHost folder may have Fabric.dll without AddOn — still useful partial
        if candidate.is_dir() and (candidate / "Lumina.Execution.Fabric.dll").is_file():
            return candidate
    return None


def deploy_fabric_addons(workspace_root: Path) -> dict[str, Any]:
    source = resolve_fabric_source_dir(workspace_root)
    dest = ninjatrader_documents_addons()
    result: dict[str, Any] = {
        "deployed": False,
        "source": str(source) if source else None,
        "destination": str(dest),
        "copied": [],
        "missing": [],
        "error": None,
    }
    if source is None:
        result["error"] = "No Fabric build artifacts found under integrations/ninjatrader8"
        result["missing"] = list(FABRIC_DLL_NAMES)
        return result
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        result["error"] = f"Cannot create NT8 AddOns folder: {exc}"
        return result

    for name in FABRIC_DLL_NAMES:
        src = source / name
        if not src.is_file():
            # Also check sibling Fabric bin
            alt = workspace_root / "integrations/ninjatrader8/Lumina.Execution.Fabric/bin/Release/net48" / name
            src = alt if alt.is_file() else src
        if not src.is_file():
            result["missing"].append(name)
            continue
        try:
            shutil.copy2(src, dest / name)
            result["copied"].append(name)
        except OSError as exc:
            result["missing"].append(name)
            logger.warning("Fabric deploy copy failed %s: %s", name, exc)

    result["deployed"] = "LuminaNt8AddOn.dll" in result["copied"] or "Lumina.Execution.Fabric.dll" in result["copied"]
    return result


def ensure_fabric_token_in_env(config_manager: Any) -> str:
    """Return token, generating + writing if absent."""
    env_values = config_manager.parse_env_file()
    token = str(env_values.get("LUMINA_FABRIC_TOKEN") or os.getenv("LUMINA_FABRIC_TOKEN") or "").strip()
    if not token:
        token = generate_fabric_token()
        config_manager.write_env_file({"LUMINA_FABRIC_TOKEN": token})
    os.environ["LUMINA_FABRIC_TOKEN"] = token
    apply_fabric_token_side_effects(token)
    write_fabric_json_defaults()
    return token


def run_fabric_bootstrap(workspace_root: Path, config_manager: Any) -> dict[str, Any]:
    """Idempotent bootstrap for Operator Vault mount / seal."""
    token = ensure_fabric_token_in_env(config_manager)
    fabric_json = write_fabric_json_defaults()
    deploy = deploy_fabric_addons(workspace_root)
    return {
        "token_ready": bool(token),
        "token_length": len(token),
        "fabric_json": str(fabric_json),
        "deploy": deploy,
        "gateway_mode": "sim",
    }
