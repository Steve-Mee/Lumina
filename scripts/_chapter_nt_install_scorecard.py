"""Final scorecard: NinjaTrader coupling + install package ready to close chapter."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lumina_launcher.services.fabric_heal import (  # noqa: E402
    _primary_custom_dir,
    clean_nt_custom_obj_pollution,
    inject_lumina_source_into_csproj,
)


def main() -> int:
    checks: list[tuple[bool, str, str]] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        checks.append((bool(cond), name, detail))
        mark = "OK  " if cond else "FAIL"
        print(f"{mark} {name}" + (f" — {detail}" if detail else ""))

    from lumina_launcher.services.fabric_deploy_integrity import (  # noqa: E402
        NT_BRIDGE_MIN_BYTES,
        collect_bridge_candidates,
        pick_best_nt_bridge,
        verify_nt_bridge_dll,
    )

    deploy = ROOT / "integrations/ninjatrader8/deploy/AddOns"
    ok("deploy has @LuminaFabricHost.cs", (deploy / "@LuminaFabricHost.cs").is_file())
    best = pick_best_nt_bridge(collect_bridge_candidates(ROOT))
    ok("product NtBridge found in workspace", best is not None, str(best))
    if best is not None:
        rep = verify_nt_bridge_dll(best)
        ok(
            f"NtBridge product integrity >= {NT_BRIDGE_MIN_BYTES}",
            bool(rep.get("ok")),
            f"size={rep.get('size')} reason={rep.get('reason')}",
        )
        ok(
            "NtBridge has Account+Hist+Live markers",
            not rep.get("missing_markers"),
            str(rep.get("missing_markers") or ""),
        )
    ok("deploy has Fabric.dll", (deploy / "Lumina.Execution.Fabric.dll").is_file())
    # Legacy LuminaNt8AddOn.dll alias is optional (must not be active dual-load).
    src = (deploy / "@LuminaFabricHost.cs").read_text(encoding="utf-8", errors="replace")
    ok("source no Shapes using", "using System.Windows.Shapes;" not in src)
    ok("source has LUMINA menu", "ControlCenterMenuItemNew" in src and 'Header = "LUMINA"' in src)
    ok("source has Link window", "class LuminaLinkWindow" in src)
    ok("source GetStatusJson", "GetStatusJson" in src)

    heal = (ROOT / "lumina_launcher/services/fabric_heal.py").read_text(encoding="utf-8")
    ok("heal sanitizes obj Compile", "obj_compile" in heal and "removed_" in heal)
    ok("heal scrubs resources.cs", "clean_nt_custom_obj_pollution" in heal)
    ok("heal builds custom", "def build_ninjatrader_custom" in heal)
    ok("heal injects source", "LuminaFabricHost" in heal)
    ok("heal satellite langs empty", "SatelliteResourceLanguages=" in heal)

    boot = (ROOT / "lumina_launcher/services/fabric_bootstrap.py").read_text(encoding="utf-8")
    ok("bootstrap uses integrity module", "verify_nt_bridge_dll" in boot or "fabric_deploy_integrity" in boot)
    ok("bootstrap copies source AddOn", "LuminaFabricHost" in boot)
    ok(
        "integrity module present",
        (ROOT / "lumina_launcher/services/fabric_deploy_integrity.py").is_file(),
    )

    c = _primary_custom_dir()
    ok("live custom found", c is not None, str(c))
    if c is not None:
        inject_lumina_source_into_csproj(c)
        clean_nt_custom_obj_pollution(c)
        text = (c / "NinjaTrader.Custom.csproj").read_text(encoding="utf-8")
        ok("live csproj Lumina", "LuminaFabricHost" in text)
        ok("live csproj no obj Include", re.search(r'Compile Include="obj\\', text) is None)
        ok("live Compile Remove obj", 'Compile Remove="obj\\**"' in text)
        dll = (c / "NinjaTrader.Custom.dll").read_bytes()
        ok("live Custom.dll Lumina types", b"LuminaFabricHost" in dll)
        ok("live Custom.dll Link window", b"LuminaLinkWindow" in dll)
        live_bridge = c / "Lumina.Fabric.NtBridge.dll"
        ok("live NtBridge present", live_bridge.is_file())
        if live_bridge.is_file():
            live_rep = verify_nt_bridge_dll(live_bridge)
            ok(
                "live NtBridge product integrity",
                bool(live_rep.get("ok")),
                f"size={live_rep.get('size')} reason={live_rep.get('reason')}",
            )
        ok("live Fabric present", (c / "Lumina.Execution.Fabric.dll").is_file())
        ok("live source AddOn", (c / "AddOns" / "@LuminaFabricHost.cs").is_file())
        ok("live no active stale Nt8AddOn dll", not (c / "LuminaNt8AddOn.dll").is_file())
        ok("live no resources.cs pollution", len(list(c.glob("obj/**/*.resources.cs"))) == 0)

    api = (ROOT / "lumina_os/backend/setup_endpoints_fabric.py").read_text(encoding="utf-8")
    ui = (ROOT / "tauri-app/src/lib/setupClient.ts").read_text(encoding="utf-8")
    actions = (
        ROOT / "tauri-app/src/components/onboarding/steps/credentialsFabricActions.ts"
    ).read_text(encoding="utf-8")
    runbook = (ROOT / "docs/runbooks/execution-fabric-operator.md").read_text(encoding="utf-8")
    ok("API fabric-heal", "fabric_heal" in api)
    ok("UI postFabricHeal", "fabric-heal" in ui)
    ok("UI Repair button path", "runFabricRepair" in actions)
    ok("runbook LUMINA Link", "LUMINA Link" in runbook)
    ok("runbook zero-IT", "Zero-IT" in runbook or "zero-IT" in runbook)

    fails = [n for good, n, _ in checks if not good]
    print()
    print(f"SCORE {len(checks) - len(fails)}/{len(checks)}")
    if fails:
        print("FAILURES:", fails)
        return 1
    print("CHAPTER NINJATRADER COUPLING + INSTALL: READY TO CLOSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
