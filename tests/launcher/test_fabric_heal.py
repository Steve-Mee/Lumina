"""Unit tests for zero-IT Fabric heal pipeline (mocked NT)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_launcher.services import fabric_heal as heal


class _CfgMgr:
    def parse_env_file(self) -> dict[str, str]:
        return {"LUMINA_FABRIC_TOKEN": "test-token-heal-xyz"}

    def write_env_file(self, _d: dict[str, str]) -> None:
        return None


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

    monkeypatch.setattr(heal, "resolve_nt_exe", lambda: fake_exe)
    monkeypatch.setattr(heal, "is_ninjatrader_running", lambda: False)
    monkeypatch.setattr(heal, "close_ninjatrader", lambda **_k: {"ok": True, "status": "not_running"})
    monkeypatch.setattr(heal, "launch_ninjatrader", lambda: {"ok": True, "status": "launched", "exe": str(fake_exe)})
    monkeypatch.setattr(
        heal,
        "wait_for_fabric_host",
        lambda **_k: {"ok": True, "status": "listening", "elapsed_sec": 1.0, "nt_host_state": "running"},
    )
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ninjatrader_custom_candidates",
        lambda: [custom],
    )
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
        lambda _root: {
            "deployed": True,
            "destination": str(custom),
            "copied": ["Custom/Lumina.Fabric.NtBridge.dll"],
            "missing": [],
            "error": None,
        },
    )
    monkeypatch.setattr(heal, "build_ninjatrader_custom", lambda _c: {"ok": True, "status": "built"})
    monkeypatch.setattr(heal, "inject_lumina_source_into_csproj", lambda _c: {"ok": True, "status": "injected"})
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_simhost.stop_simhost",
        lambda **_k: {"ok": True, "killed": []},
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

    monkeypatch.setattr(heal, "resolve_nt_exe", lambda: fake_exe)
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
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ninjatrader_custom_candidates",
        lambda: [custom],
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ensure_fabric_token_in_env",
        lambda _cm: "tok",
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.deploy_fabric_addons",
        lambda _root: {
            "deployed": True,
            "destination": str(custom),
            "copied": ["Custom/Lumina.Fabric.NtBridge.dll"],
            "missing": [],
            "error": None,
        },
    )
    monkeypatch.setattr(heal, "build_ninjatrader_custom", lambda _c: {"ok": True, "status": "built"})
    monkeypatch.setattr(heal, "inject_lumina_source_into_csproj", lambda _c: {"ok": True, "status": "injected"})
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_simhost.stop_simhost",
        lambda **_k: {"ok": True, "killed": []},
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

    monkeypatch.setattr(heal, "resolve_nt_exe", lambda: fake_exe)
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
    monkeypatch.setattr(heal, "_primary_custom_dir", lambda: custom)
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ninjatrader_custom_candidates",
        lambda: [custom],
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.ensure_fabric_token_in_env",
        lambda _cm: "tok",
    )
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_bootstrap.deploy_fabric_addons",
        lambda _root: {
            "deployed": True,
            "destination": str(custom),
            "copied": ["Custom/Lumina.Fabric.NtBridge.dll"],
            "missing": [],
            "error": None,
        },
    )
    monkeypatch.setattr(heal, "build_ninjatrader_custom", lambda _c: {"ok": True, "status": "built"})
    monkeypatch.setattr(heal, "inject_lumina_source_into_csproj", lambda _c: {"ok": True, "status": "injected"})
    monkeypatch.setattr(
        "lumina_launcher.services.fabric_simhost.stop_simhost",
        lambda **_k: {"ok": True, "killed": []},
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


def test_promote_staged_dlls(tmp_path: Path) -> None:
    custom = tmp_path / "Custom"
    custom.mkdir()
    staged = custom / "Lumina.Fabric.NtBridge.dll.new"
    staged.write_bytes(b"new")
    promoted = heal.promote_staged_dlls(custom)
    assert "Lumina.Fabric.NtBridge.dll" in promoted
    assert (custom / "Lumina.Fabric.NtBridge.dll").is_file()
    assert not staged.is_file()
