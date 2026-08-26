"""Vault emergency checkbox must write broker.fallback_on_fabric_failure."""

from __future__ import annotations

from pathlib import Path

import yaml

from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.services.setup_persist_credentials import (
    build_credentials_env_snapshot,
    persist_credentials_only,
)


def test_persist_credentials_writes_emergency_flag(tmp_path: Path, monkeypatch) -> None:
    cfg = tmp_path / "config.yaml"
    env = tmp_path / ".env"
    cfg.write_text(
        yaml.dump(
            {
                "broker": {
                    "live_provider": "ninjatrader",
                    "fallback_on_fabric_failure": False,
                    "ninjatrader": {"enabled": True},
                }
            }
        ),
        encoding="utf-8",
    )
    env.write_text("", encoding="utf-8")
    monkeypatch.setenv("LUMINA_CONFIG", str(cfg))
    monkeypatch.delenv("BROKER_FALLBACK_ON_FABRIC_FAILURE", raising=False)

    cm = ConfigManager(env_path=env, config_path=cfg)
    persist_credentials_only(
        cm,
        {
            "LUMINA_JWT_SECRET_KEY": "x" * 40,
            "LUMINA_FABRIC_TOKEN": "fabric-tok",
        },
        emergency_market_data_fallback=True,
        workspace_root=tmp_path,
    )
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data["broker"]["fallback_on_fabric_failure"] is True
    assert data["broker"]["live_provider"] == "ninjatrader"

    snap = build_credentials_env_snapshot(cm)
    assert snap["emergency_market_data_fallback"] is True

    persist_credentials_only(
        cm,
        {"LUMINA_JWT_SECRET_KEY": "x" * 40, "LUMINA_FABRIC_TOKEN": "fabric-tok"},
        emergency_market_data_fallback=False,
        workspace_root=tmp_path,
    )
    data2 = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data2["broker"]["fallback_on_fabric_failure"] is False
