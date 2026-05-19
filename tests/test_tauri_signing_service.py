from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.services.tauri_signing_service import (
    ENV_SIGNING_KEY_PATH,
    TauriSigningService,
    default_key_path,
    is_configured,
    persist_to_env,
    read_public_key,
    sync_pubkey_to_tauri_conf,
)


@pytest.mark.unit
def test_is_configured_requires_file_and_env(tmp_path: Path) -> None:
    key_path = default_key_path(tmp_path)
    assert is_configured(tmp_path, {}) is False
    assert is_configured(tmp_path, {ENV_SIGNING_KEY_PATH: "state/lumina-tauri-signing.key"}) is False

    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private", encoding="utf-8")
    assert is_configured(tmp_path, {ENV_SIGNING_KEY_PATH: "state/lumina-tauri-signing.key"}) is True


@pytest.mark.unit
def test_persist_to_env_writes_path(tmp_path: Path) -> None:
    key_path = default_key_path(tmp_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private", encoding="utf-8")

    config_manager = ConfigManager(tmp_path / ".env", tmp_path / "config.yaml")
    relative = persist_to_env(config_manager, key_path, tmp_path)

    assert relative == "state/lumina-tauri-signing.key"
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "TAURI_SIGNING_PRIVATE_KEY_PATH=state/lumina-tauri-signing.key" in env_text


@pytest.mark.unit
def test_sync_pubkey_updates_tauri_conf(tmp_path: Path) -> None:
    conf_dir = tmp_path / "tauri-app" / "src-tauri"
    conf_dir.mkdir(parents=True)
    conf_path = conf_dir / "tauri.conf.json"
    conf_path.write_text(
        json.dumps({"plugins": {"updater": {"pubkey": "old-key", "endpoints": []}}}),
        encoding="utf-8",
    )

    sync_pubkey_to_tauri_conf(tmp_path, "new-public-key")

    payload = json.loads(conf_path.read_text(encoding="utf-8"))
    assert payload["plugins"]["updater"]["pubkey"] == "new-public-key"


@pytest.mark.unit
def test_read_public_key(tmp_path: Path) -> None:
    key_path = tmp_path / "state" / "lumina-tauri-signing.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path = Path(f"{key_path}.pub")
    pub_path.write_text("abc123pub", encoding="utf-8")

    assert read_public_key(key_path) == "abc123pub"


@pytest.mark.integration
def test_generate_keypair_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil

    if shutil.which("npm") is None:
        pytest.skip("npm not available")

    tauri_dir = tmp_path / "tauri-app"
    tauri_dir.mkdir(parents=True)
    (tauri_dir / "package.json").write_text('{"name":"tauri-app"}', encoding="utf-8")
    conf_dir = tauri_dir / "src-tauri"
    conf_dir.mkdir(parents=True)
    (conf_dir / "tauri.conf.json").write_text(
        json.dumps({"plugins": {"updater": {"pubkey": "old", "endpoints": []}}}),
        encoding="utf-8",
    )

    key_path = default_key_path(tmp_path)

    def fake_run(command, **kwargs):
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text("private-key-content", encoding="utf-8")
        Path(f"{key_path}.pub").write_text("generated-public-key", encoding="utf-8")

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Result()

    monkeypatch.setattr("lumina_launcher.services.tauri_signing_service.subprocess.run", fake_run)

    config_manager = ConfigManager(tmp_path / ".env", tmp_path / "config.yaml")
    service = TauriSigningService(tmp_path)
    result = service.generate_keypair(config_manager=config_manager, force=True)

    assert result.success, result.message
    assert key_path.is_file()
    assert is_configured(tmp_path, config_manager.parse_env_file())
    conf_payload = json.loads((conf_dir / "tauri.conf.json").read_text(encoding="utf-8"))
    assert conf_payload["plugins"]["updater"]["pubkey"] == "generated-public-key"
