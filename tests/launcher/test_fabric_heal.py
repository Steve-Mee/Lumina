"""Unit tests for zero-IT Fabric heal pipeline (mocked NT)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_launcher.services import fabric_heal as heal


class _CfgMgr:
    def parse_env_file(self) -> dict[str, str]:
        return {"LUMINA_FABRIC_TOKEN": "test-token-heal-xyz"}

    def write_env_file(self, _d: dict[str, str]) -> None:
        return None


def _deploy_ok(destination: Path) -> dict[str, Any]:
    """Deploy result shape matching current integrity-gated heal path."""
    return {
        "deployed": True,
        "destination": str(destination),
        "copied": ["Custom/Lumina.Fabric.NtBridge.dll"],
        "missing": [],
        "error": None,
        "destinations": [],
        "integrity": {
            "bridge_source": {
                "ok": True,
                "size": 50_000,
                "sha256": "abc123def456",
                "reason": "ok",
            }
        },
    }


def _patch_heal_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake_exe: Path,
    custom: Path,
    addons_src: Path | None = None,
) -> None:
    """Common mocks so heal never talks to a real Fabric host / NT process."""
    monkeypatch.setattr(heal, "resolve_nt_exe", lambda: fake_exe)
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ninjatrader_custom_candidates",
        lambda: [custom],
    )
    if addons_src is not None:
        monkeypatch.setattr(
            "lumina_launcher.services.fabric_bootstrap.resolve_fabric_source_dir",
            lambda _root: addons_src,
        )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ensure_fabric_token_in_env",
        lambda _cm: "test-token-heal-xyz",
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.deploy_fabric_addons",
        lambda _root: _deploy_ok(custom),
    )
    monkeypatch.setattr(heal, "build_ninjatrader_custom", lambda _c: {"ok": True, "status": "built"})
    monkeypatch.setattr(heal, "inject_lumina_source_into_csproj", lambda _c: {"ok": True, "status": "injected"})
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_simhost.stop_simhost",
        lambda **_k: {"ok": True, "killed": []},
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_link_ensure.ensure_fabric_token_aligned_and_live",
        lambda **_k: {"ok": True, "code": "OK", "message": "mocked"},
    )


def test_heal_fails_when_nt_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(heal, "resolve_nt_exe", lambda: None)
    report = heal.run_fabric_heal(tmp_path, _CfgMgr(), run_diagnostic=False, launch_ninjatrader_flag=False)
    assert report.ok is False
    assert report.overall == "red"
    assert any(s.id == "detect_nt" and s.status == "fail" for s in report.steps)
    assert any(n["code"] == "install_nt" for n in report.needs_user)


def test_heal_deploys_and_skips_diag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_exe = tmp_path / "NinjaTrader.exe"
    fake_exe.write_bytes(b"x")
    custom = tmp_path / "Documents" / "NinjaTrader 8" / "bin" / "Custom"
    custom.mkdir(parents=True)
    (custom / "NinjaTrader.Custom.csproj").write_text(
        '<?xml version="1.0"?><Project Sdk="Microsoft.NET.Sdk"><ItemGroup></ItemGroup></Project>',
        encoding="utf-8",
    )
    addons_src = tmp_path / "integrations" / "ninjatrader8" / "deploy" / "AddOns"
    addons_src.mkdir(parents=True)
    (addons_src / "Lumina.Fabric.NtBridge.dll").write_bytes(b"bridge")
    (addons_src / "Lumina.Execution.Fabric.dll").write_bytes(b"fabric")

    _patch_heal_happy_path(monkeypatch, fake_exe=fake_exe, custom=custom, addons_src=addons_src)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    monkeypatch.setattr(heal, "close_ninjatrader", lambda **_k: {"ok": True, "status": "not_running"})
    monkeypatch.setattr(heal, "launch_ninjatrader", lambda: {"ok": True, "status": "launched", "exe": str(fake_exe)})
    monkeypatch.setattr(
        heal,
        "wait_for_fabric_host",
        lambda **_k: {"ok": True, "status": "listening", "elapsed_sec": 1.0, "nt_host_state": "running"},
    )

    report = heal.run_fabric_heal(
        tmp_path,
        _CfgMgr(),
        close_nt=True,
        launch_ninjatrader_flag=True,
        run_diagnostic=False,
        force_redeploy=True,
    )
    assert any(s.id == "deploy" and s.status == "pass" for s in report.steps)
    assert any(s.id == "launch_nt" and s.status == "pass" for s in report.steps)
    assert any(s.id == "wait_host" and s.status == "pass" for s in report.steps)


def test_soft_heal_does_not_close_running_nt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Soft setup (close_nt=False) must never taskkill a running NinjaTrader."""
    fake_exe = tmp_path / "NinjaTrader.exe"
    fake_exe.write_bytes(b"x")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "NinjaTrader.Custom.csproj").write_text(
        '<?xml version="1.0"?><Project Sdk="Microsoft.NET.Sdk"><ItemGroup></ItemGroup></Project>',
        encoding="utf-8",
    )
    closed: list[Any] = []

    _patch_heal_happy_path(monkeypatch, fake_exe=fake_exe, custom=custom)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: True)
    monkeypatch.setattr(
        heal,
        "close_ninjatrader",
        lambda **k: closed.append(k) or {"ok": True, "status": "stopped"},
    )
    monkeypatch.setattr(heal, "launch_ninjatrader", lambda: {"ok": True, "status": "launched", "exe": str(fake_exe)})
    monkeypatch.setattr(
        heal,
        "wait_for_fabric_host",
        lambda **_k: {"ok": True, "status": "listening", "elapsed_sec": 0.1, "nt_host_state": "running"},
    )

    report = heal.run_fabric_heal(
        tmp_path,
        _CfgMgr(),
        close_nt=False,
        launch_ninjatrader_flag=True,
        run_diagnostic=False,
    )
    assert closed == [], f"soft heal must not close NT, got {closed}"
    assert any(s.id == "close_nt" and s.status == "skip" for s in report.steps)
    assert any(s.id == "launch_nt" and s.status == "skip" for s in report.steps)


def test_heal_closes_nt_when_running_no_bool_callable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Regression: param must not shadow close_ninjatrader() → TypeError bool not callable."""
    fake_exe = tmp_path / "NinjaTrader.exe"
    fake_exe.write_bytes(b"x")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "NinjaTrader.Custom.csproj").write_text(
        '<?xml version="1.0"?><Project Sdk="Microsoft.NET.Sdk"><ItemGroup></ItemGroup></Project>',
        encoding="utf-8",
    )
    closed: list[dict[str, Any]] = []

    _patch_heal_happy_path(monkeypatch, fake_exe=fake_exe, custom=custom)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: True)
    monkeypatch.setattr(
        heal,
        "close_ninjatrader",
        lambda **k: closed.append(k) or {"ok": True, "status": "stopped"},
    )
    monkeypatch.setattr(heal, "launch_ninjatrader", lambda: {"ok": True, "status": "launched", "exe": str(fake_exe)})
    monkeypatch.setattr(
        heal,
        "wait_for_fabric_host",
        lambda **_k: {"ok": True, "status": "listening", "elapsed_sec": 0.1, "nt_host_state": "running"},
    )

    report = heal.run_fabric_heal(
        tmp_path,
        _CfgMgr(),
        close_nt=True,  # explicit Repair path
        launch_ninjatrader_flag=True,
        run_diagnostic=False,
    )
    assert closed, "close_ninjatrader() must be invoked when NT is running and close_nt=True"
    assert any(s.id == "close_nt" and s.status == "pass" for s in report.steps)
    assert report.ok is not False or any(s.status == "pass" for s in report.steps)

    # Default close_nt=False must not kill even when NT is running
    closed.clear()
    report2 = heal.run_fabric_heal(
        tmp_path,
        _CfgMgr(),
        # close_nt defaults False
        launch_ninjatrader_flag=True,
        run_diagnostic=False,
    )
    assert closed == [], f"default heal must not close NT: {closed}"
    assert any(s.id == "close_nt" and s.status == "skip" for s in report2.steps)


def test_retarget_818_installer_csproj(tmp_path: Path) -> None:
    """NT 8.1.8.3 installer drops a source-tree csproj; retarget to installed bin."""
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    for name in (
        "NinjaTrader.Core.dll",
        "NinjaTrader.Gui.dll",
        "Infralution.Localization.Wpf.dll",
        "SharpDX.dll",
        "SharpDX.Direct2D1.dll",
    ):
        (nt_bin / name).write_bytes(b"MZ")
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="SharpDX">
      <HintPath>..\\NinjaTrader\\DirectX\\SharpDX.dll</HintPath>
    </Reference>
    <Reference Include="SharpDX.Direct2D1">
      <HintPath>..\\NinjaTrader\\DirectX\\SharpDX.Direct2D1.dll</HintPath>
    </Reference>
  </ItemGroup>
  <ItemGroup>
    <ProjectReference Include="..\\External\\Infralution\\Infralution.Localization.Wpf.csproj" />
    <ProjectReference Include="..\\NinjaTrader.Core\\NinjaTrader.Core.csproj" />
    <ProjectReference Include="..\\NinjaTrader.Gui\\NinjaTrader.Gui.csproj" />
  </ItemGroup>
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    text, notes = heal._retarget_nt_custom_csproj(src, nt_bin)
    assert "NinjaTrader.Core.csproj" not in text
    assert "NinjaTrader.Gui.csproj" not in text
    assert "Infralution.Localization.Wpf.csproj" not in text
    assert str(nt_bin / "NinjaTrader.Core.dll") in text
    assert str(nt_bin / "NinjaTrader.Gui.dll") in text
    assert str(nt_bin / "SharpDX.dll") in text
    assert "..\\NinjaTrader\\DirectX" not in text
    assert any("removed_projectref_NinjaTrader.Core" in n for n in notes)
    assert any("sharpdx" in n for n in notes)
    # Retarget itself does not add Newtonsoft; sanitize/ensure does.
    assert "Newtonsoft.Json" not in text


def test_sanitize_adds_newtonsoft_from_nt_bin(tmp_path: Path) -> None:
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"MZ")
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
    <Compile Include="Strategies\\NewsPostReleaseBreakoutBotUnmanaged.cs" />
  </ItemGroup>
</Project>
"""
    text, notes = heal._sanitize_nt_custom_csproj(src, nt_bin)
    assert '<Reference Include="Newtonsoft.Json">' in text
    assert str(nt_bin / "Newtonsoft.Json.dll") in text
    assert "<Private>False</Private>" in text
    assert any("added_ref_Newtonsoft.Json" in n for n in notes)
    again, notes2 = heal._sanitize_nt_custom_csproj(text, nt_bin)
    assert again.count('<Reference Include="Newtonsoft.Json">') == 1
    assert not any("added_ref_Newtonsoft.Json" in n for n in notes2)


def test_sanitize_prefers_custom_newtonsoft_over_nt_bin(tmp_path: Path) -> None:
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"NT")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "Newtonsoft.Json.dll").write_bytes(b"CUSTOM")
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    text, notes = heal._sanitize_nt_custom_csproj(src, nt_bin, custom)
    assert str(custom / "Newtonsoft.Json.dll") in text
    assert str(nt_bin / "Newtonsoft.Json.dll") not in text
    assert any("added_ref_Newtonsoft.Json" in n for n in notes)


def test_retarget_newtonsoft_hintpath_from_program_files(tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    dll = custom / "Newtonsoft.Json.dll"
    dll.write_bytes(b"CUSTOM")
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Reference Include="Newtonsoft.Json">
      <SpecificVersion>False</SpecificVersion>
      <HintPath>C:\\Program Files\\NinjaTrader 8\\bin\\Newtonsoft.Json.dll</HintPath>
      <Private>False</Private>
    </Reference>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    text, notes = heal._sanitize_nt_custom_csproj(src, None, custom)
    assert str(dll) in text
    assert "Program Files" not in text
    assert any("retargeted_ref_Newtonsoft.Json" in n for n in notes)
    assert text.count('<Reference Include="Newtonsoft.Json">') == 1


def test_config_xml_adds_newtonsoft(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    nt8 = tmp_path / "NinjaTrader 8"
    custom = nt8 / "bin" / "Custom"
    custom.mkdir(parents=True)
    (custom / "Newtonsoft.Json.dll").write_bytes(b"MZ")
    config = nt8 / "Config.xml"
    config.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<NinjaTrader>
  <References>
    <ArrayOfString xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <string>System.dll</string>
      <string>*MyDocuments*\\NinjaTrader 8\\bin\\Custom\\NinjaTrader.Vendor.dll</string>
    </ArrayOfString>
  </References>
</NinjaTrader>
""",
        encoding="utf-8",
    )
    r = heal.ensure_ninjascript_config_references(custom)
    assert r["ok"] is True
    assert r["changed"] is True
    assert r["status"] == "added"
    body = config.read_text(encoding="utf-8-sig")
    assert "*MyDocuments*\\NinjaTrader 8\\bin\\Custom\\Newtonsoft.Json.dll" in body
    r2 = heal.ensure_ninjascript_config_references(custom)
    assert r2["changed"] is False
    assert r2["status"] == "already_present"
    assert body.count("Newtonsoft.Json.dll") == config.read_text(encoding="utf-8-sig").count(
        "Newtonsoft.Json.dll"
    )


def test_config_xml_skips_write_while_nt_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: True)
    nt8 = tmp_path / "NinjaTrader 8"
    custom = nt8 / "bin" / "Custom"
    custom.mkdir(parents=True)
    (custom / "Newtonsoft.Json.dll").write_bytes(b"MZ")
    config = nt8 / "Config.xml"
    original = "<NinjaTrader><References><ArrayOfString /></References></NinjaTrader>"
    config.write_text(original, encoding="utf-8")
    r = heal.ensure_ninjascript_config_references(custom)
    assert r["status"] == "skipped_nt_running"
    assert r["changed"] is False
    assert config.read_text(encoding="utf-8") == original


def test_replace_netstandard_newtonsoft_when_nt_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"MZ-NETFX-NEWTONSOFT")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "Newtonsoft.Json.dll").write_bytes(b"MZ.NETStandard,Version=v2.0-CUSTOM")
    notes = heal._ensure_well_known_dlls_in_custom(custom, nt_bin)
    assert any("replaced_netstandard_Newtonsoft.Json.dll" in n for n in notes)
    assert (custom / "Newtonsoft.Json.dll").read_bytes() == b"MZ-NETFX-NEWTONSOFT"


def test_skip_replace_netstandard_newtonsoft_while_nt_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: True)
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"MZ-NETFX")
    custom = tmp_path / "Custom"
    custom.mkdir()
    original = b"MZ.NETStandard,Version=v2.0-KEEP"
    (custom / "Newtonsoft.Json.dll").write_bytes(original)
    notes = heal._ensure_well_known_dlls_in_custom(custom, nt_bin)
    assert any("skipped_replace_nt_running_Newtonsoft.Json.dll" in n for n in notes)
    assert (custom / "Newtonsoft.Json.dll").read_bytes() == original


def test_config_xml_adds_netstandard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    nt8 = tmp_path / "NinjaTrader 8"
    custom = nt8 / "bin" / "Custom"
    custom.mkdir(parents=True)
    (custom / "netstandard.dll").write_bytes(b"MZ")
    config = nt8 / "Config.xml"
    config.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<NinjaTrader>
  <References>
    <ArrayOfString xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
      <string>System.dll</string>
    </ArrayOfString>
  </References>
</NinjaTrader>
""",
        encoding="utf-8",
    )
    r = heal.ensure_ninjascript_config_references(custom)
    assert r["ok"] is True
    assert r["changed"] is True
    body = config.read_text(encoding="utf-8-sig")
    assert "*MyDocuments*\\NinjaTrader 8\\bin\\Custom\\netstandard.dll" in body


def test_sanitize_skips_newtonsoft_when_dll_missing(tmp_path: Path) -> None:
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    text, notes = heal._sanitize_nt_custom_csproj(src, nt_bin)
    assert "Newtonsoft.Json" not in text
    assert any("skipped_missing_Newtonsoft.Json" in n for n in notes)


def test_isolate_third_party_keeps_lumina_host() -> None:
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />
    <Compile Include="Strategies\\NewsPostReleaseBreakoutBotUnmanaged.cs" />
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    log = (
        r"Strategies\NewsPostReleaseBreakoutBotUnmanaged.cs(26,7): error CS0246: "
        "The type or namespace name 'Newtonsoft' could not be found\n"
        r"Strategies\NewsPostReleaseBreakoutBotUnmanaged.cs(185,36): error CS0103: "
        "The name 'JsonConvert' does not exist in the current context\n"
    )
    text, isolated = heal.isolate_failing_third_party_scripts(src, log)
    assert isolated == ["NewsPostReleaseBreakoutBotUnmanaged.cs"]
    assert "NewsPostReleaseBreakoutBotUnmanaged.cs" not in text
    assert "LuminaFabricHost" in text
    assert "AssemblyInfo.cs" in text


def test_isolate_never_drops_lumina_or_stock_scripts() -> None:
    src = """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />
    <Compile Include="Indicators\\%40ADX.cs" />
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
"""
    log = (
        r"AddOns\%40LuminaFabricHost.cs(10,1): error CS0246: missing\n"
        r"Indicators\%40ADX.cs(2,1): error CS0103: x\n"
        r"AssemblyInfo.cs(1,1): error CS0579: duplicate\n"
    )
    text, isolated = heal.isolate_failing_third_party_scripts(src, log)
    assert isolated == []
    assert "LuminaFabricHost" in text
    assert "%40ADX.cs" in text
    assert "AssemblyInfo.cs" in text


def test_inject_818_template_retargets_and_adds_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "NinjaTrader.Core.dll").write_bytes(b"MZ")
    (nt_bin / "NinjaTrader.Gui.dll").write_bytes(b"MZ")
    (nt_bin / "Infralution.Localization.Wpf.dll").write_bytes(b"MZ")
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"MZ")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "AddOns").mkdir()
    csproj = custom / "NinjaTrader.Custom.csproj"
    csproj.write_text(
        """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <ProjectReference Include="..\\NinjaTrader.Core\\NinjaTrader.Core.csproj" />
    <ProjectReference Include="..\\NinjaTrader.Gui\\NinjaTrader.Gui.csproj" />
  </ItemGroup>
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(heal, "_nt_bin_dir", lambda: nt_bin)
    r = heal.inject_lumina_source_into_csproj(custom)
    assert r["ok"] is True
    text = csproj.read_text(encoding="utf-8")
    assert "LuminaFabricHost" in text
    assert "NinjaTrader.Core.csproj" not in text
    assert str(nt_bin / "NinjaTrader.Core.dll") in text
    assert (custom / "Newtonsoft.Json.dll").is_file()
    assert str(custom / "Newtonsoft.Json.dll") in text


def test_inject_csproj(tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "AddOns").mkdir()
    csproj = custom / "NinjaTrader.Custom.csproj"
    csproj.write_text(
        """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    r = heal.inject_lumina_source_into_csproj(custom)
    assert r["ok"] is True
    text = csproj.read_text(encoding="utf-8")
    assert "LuminaFabricHost" in text
    r2 = heal.inject_lumina_source_into_csproj(custom)
    assert r2["status"] == "already_present"


def test_sanitize_removes_obj_assembly_attributes(tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    csproj = custom / "NinjaTrader.Custom.csproj"
    csproj.write_text(
        """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
    <Compile Include="obj\\x64\\Debug\\.NETFramework,Version=v4.8.AssemblyAttributes.cs" />
    <Compile Include="obj\\x64\\Release\\de-DE\\NinjaTrader.Custom.resources.cs" />
    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />
  </ItemGroup>
  <ItemGroup>
    <None Remove="obj\\**" />
    <Page Remove="obj\\**" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    r = heal.inject_lumina_source_into_csproj(custom)
    assert r["ok"] is True
    text = csproj.read_text(encoding="utf-8")
    assert "AssemblyAttributes" not in text
    assert "resources.cs" not in text
    assert 'Compile Include="obj\\' not in text
    assert "LuminaFabricHost" in text
    assert 'Compile Remove="obj\\**"' in text
    assert "sanitized" in str(r.get("status") or "")


def test_clean_obj_pollution_removes_resources_cs(tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    obj = custom / "obj" / "x64" / "Release" / "de-DE"
    obj.mkdir(parents=True)
    junk = obj / "NinjaTrader.Custom.resources.cs"
    junk.write_text('[assembly: System.Reflection.AssemblyTitleAttribute("x")]\n', encoding="utf-8")
    attr = custom / "obj" / "x64" / "Debug" / ".NETFramework,Version=v4.8.AssemblyAttributes.cs"
    attr.parent.mkdir(parents=True, exist_ok=True)
    attr.write_text("// attrs\n", encoding="utf-8")
    r = heal.clean_nt_custom_obj_pollution(custom)
    assert r["ok"] is True
    assert not junk.is_file()
    assert not attr.is_file()
    assert len(r["removed"]) >= 2


def test_promote_staged_dlls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    staged = custom / "Lumina.Fabric.NtBridge.dll.new"
    # Product bridge must clear size + marker integrity; use a valid-sized fixture.
    markers = b"FabricNtHost NtAccountOrderGateway NtHistoricalDataProvider NtLiveMarketDataProvider NtLiveBarProvider"
    staged.write_bytes(markers + b"\0" * (40_000 - len(markers)))
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    promoted = heal.promote_staged_dlls(custom)
    assert any(Path(p).name == "Lumina.Fabric.NtBridge.dll" for p in promoted)
    assert (custom / "Lumina.Fabric.NtBridge.dll").is_file()
    assert not staged.is_file()


def test_ensure_custom_skips_build_while_nt_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    nt_bin = tmp_path / "NTBin"
    nt_bin.mkdir()
    (nt_bin / "Newtonsoft.Json.dll").write_bytes(b"MZ")
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "AddOns").mkdir()
    (custom / "NinjaTrader.Custom.csproj").write_text(
        """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AssemblyInfo.cs" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    built: list[Path] = []
    closed: list[object] = []
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(heal, "_nt_bin_dir", lambda: nt_bin)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: True)
    monkeypatch.setattr(
        heal,
        "build_ninjatrader_custom",
        lambda c: built.append(c) or {"ok": True, "status": "built"},
    )
    monkeypatch.setattr(
        heal,
        "close_ninjatrader",
        lambda **k: closed.append(k) or {"ok": True, "status": "stopped"},
    )
    r = heal.ensure_custom_compile_ready(build_if_nt_stopped=True)
    assert r["ok"] is True
    assert r["csproj_changed"] is True
    assert r["built"] is False
    assert r["build"]["status"] == "skipped_nt_running"
    assert built == []
    assert closed == []
    text = (custom / "NinjaTrader.Custom.csproj").read_text(encoding="utf-8")
    assert "LuminaFabricHost" in text
    assert "Newtonsoft.Json" in text


def test_ensure_custom_builds_when_dll_missing_and_nt_stopped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    (custom / "AddOns").mkdir()
    (custom / "NinjaTrader.Custom.csproj").write_text(
        """<?xml version="1.0"?>
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <Compile Include="AddOns\\%40LuminaFabricHost.cs" />
  </ItemGroup>
</Project>
""",
        encoding="utf-8",
    )
    built: list[Path] = []
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(heal, "_nt_bin_dir", lambda: None)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    monkeypatch.setattr(
        heal,
        "build_ninjatrader_custom",
        lambda c: built.append(c) or {"ok": True, "status": "built"},
    )
    r = heal.ensure_custom_compile_ready()
    assert r["ok"] is True
    assert r["built"] is True
    assert built == [custom]
