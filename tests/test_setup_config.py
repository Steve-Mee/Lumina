from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumina_launcher.core.setup_config import SetupConfig


@pytest.mark.unit
def test_from_workspace_defaults(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"mode": "sim"}), encoding="utf-8")
    cfg = SetupConfig.from_workspace(tmp_path)
    assert cfg.mode == "smart"
    assert cfg.auto_install_ollama is True
    assert cfg.auto_download_model is True
    assert cfg.allow_force_tier is False


@pytest.mark.unit
def test_from_workspace_reads_setup_block(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "setup": {
                    "mode": "manual",
                    "auto_install_ollama": False,
                    "auto_download_model": False,
                    "allow_force_tier": True,
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = SetupConfig.from_workspace(tmp_path)
    assert cfg.mode == "manual"
    assert cfg.auto_install_ollama is False
    assert cfg.allow_force_tier is True


@pytest.mark.unit
def test_manual_mode_disables_auto_flags_in_options() -> None:
    cfg = SetupConfig(mode="manual", auto_install_ollama=True, auto_download_model=True)
    opts = cfg.to_smart_setup_options()
    assert opts.install_ollama is False
    assert opts.download_recommended_model is False


@pytest.mark.unit
def test_invalid_mode_falls_back_to_smart() -> None:
    cfg = SetupConfig.from_dict({"mode": "experimental"})
    assert cfg.mode == "smart"


@pytest.mark.unit
def test_skips_smart_setup_wizard_only_for_classic() -> None:
    assert SetupConfig(mode="classic").skips_smart_setup_wizard() is True
    assert SetupConfig(mode="smart").skips_smart_setup_wizard() is False
    assert SetupConfig(mode="manual").skips_smart_setup_wizard() is False
