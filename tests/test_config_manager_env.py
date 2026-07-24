from __future__ import annotations

from pathlib import Path

import pytest

from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.services.setup_persist import scan_missing_credentials


@pytest.mark.unit
def test_parse_env_file_strips_bom_from_key(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LUMINA_JWT_SECRET_KEY=jwt\n"
        "LUMINA_FABRIC_TOKEN=fabric-test-token\n"
        "\ufeffCROSSTRADE_ACCOUNT=DEMO5042070   # sim account\n"
        "CROSSTRADE_TOKEN=token\n",
        encoding="utf-8",
    )
    manager = ConfigManager(env_path, tmp_path / "config.yaml")
    values = manager.parse_env_file()
    assert values["CROSSTRADE_ACCOUNT"] == "DEMO5042070"
    assert scan_missing_credentials(manager) == []


@pytest.mark.unit
def test_parse_env_file_strips_utf8_sig_file_bom(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_bytes(
        b"\xef\xbb\xbfLUMINA_JWT_SECRET_KEY=jwt\n"
        b"LUMINA_FABRIC_TOKEN=fabric-test-token\n"
        b"CROSSTRADE_TOKEN=tok\n"
        b"CROSSTRADE_ACCOUNT=acct\n"
    )
    manager = ConfigManager(env_path, tmp_path / "config.yaml")
    assert manager.parse_env_file()["LUMINA_JWT_SECRET_KEY"] == "jwt"
    assert scan_missing_credentials(manager) == []
