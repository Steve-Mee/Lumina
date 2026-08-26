"""One-shot: sanitize + rebuild NinjaTrader.Custom and verify no CS0579 pollution."""
from __future__ import annotations

import re
import sys
from pathlib import Path

# repo root
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lumina_launcher.services.fabric_heal import (  # noqa: E402
    _primary_custom_dir,
    build_ninjatrader_custom,
    clean_nt_custom_obj_pollution,
    inject_lumina_source_into_csproj,
)


def main() -> int:
    c = _primary_custom_dir()
    if c is None:
        print("FAIL: no custom dir")
        return 1
    print("custom", c)

    inj = inject_lumina_source_into_csproj(c)
    print("inject", inj)
    scrub = clean_nt_custom_obj_pollution(c)
    print("scrub", scrub)

    csproj = c / "NinjaTrader.Custom.csproj"
    text = csproj.read_text(encoding="utf-8")
    obj_compiles = re.findall(r'Compile Include="obj\\[^"]+"', text)
    print("obj Compile includes remaining:", obj_compiles)
    print("has Compile Remove obj:", 'Compile Remove="obj\\**"' in text)
    print("has LuminaFabricHost:", "LuminaFabricHost" in text)
    if obj_compiles:
        print("FAIL: still have obj Compile includes after inject")
        return 1

    r = build_ninjatrader_custom(c)
    print(
        "build ok",
        r.get("ok"),
        "status",
        r.get("status"),
        "rc",
        r.get("returncode"),
    )
    print("sanitize_pre", r.get("sanitize_pre"))
    print("sanitize_post", r.get("sanitize_post"))
    print(
        "obj_scrub removed count",
        len((r.get("obj_scrub") or {}).get("removed") or []),
    )

    text2 = csproj.read_text(encoding="utf-8")
    obj_compiles2 = re.findall(r'Compile Include="obj\\[^"]+"', text2)
    print("POST obj Compile includes:", obj_compiles2)
    res_cs = list(c.glob("obj/**/*.resources.cs"))
    attrs = list(c.glob("obj/**/*AssemblyAttributes.cs"))
    print("POST resources.cs count", len(res_cs))
    print("POST AssemblyAttributes count", len(attrs))

    if obj_compiles2:
        print("FAIL: still have obj Compile includes after build")
        return 1

    # Only AssemblyInfo (or similar single source) should define assembly attrs in Compile list
    compile_files = re.findall(r'<Compile Include="([^"]+)"', text2)
    asm_attr_files: list[str] = []
    for rel in compile_files:
        p = c / Path(rel.replace("%40", "@"))
        if not p.is_file():
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if (
            "AssemblyTitle" in t
            or "AssemblyCompanyAttribute" in t
            or "assembly: AssemblyVersion" in t
            or "AssemblyCompany(" in t
        ):
            asm_attr_files.append(rel)
    print("Compile files defining assembly attrs:", asm_attr_files)
    if len(asm_attr_files) > 1:
        print("FAIL: multiple assembly-attribute sources in Compile list")
        return 1

    dll = c / "NinjaTrader.Custom.dll"
    data = dll.read_bytes()
    has_host = b"LuminaFabricHost" in data
    has_win = b"LuminaLinkWindow" in data
    print("DLL has LuminaFabricHost", has_host, "LuminaLinkWindow", has_win, "size", len(data))
    if not has_host or not has_win:
        print("FAIL: Lumina types missing from Custom DLL")
        return 1

    if not r.get("ok"):
        print("LOG TAIL:")
        print((r.get("log_tail") or "")[-2000:])
        print("FAIL: build failed")
        return 1

    # Extra: ensure no Compile path still points at resources.cs anywhere
    if "resources.cs" in text2.lower() and "Compile Include" in text2:
        for line in text2.splitlines():
            if "Compile Include" in line and "resources.cs" in line.lower():
                print("FAIL: Compile still includes resources.cs:", line.strip())
                return 1

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
