from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest
import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "TRADER_LEAGUE_DATABASE_URL",
    f"sqlite:///{Path(__file__).parent / 'test_trader_league.db'}",
)
os.environ.setdefault(
    "TRADER_LEAGUE_RECONCILIATION_STATUS_FILE",
    str(Path(__file__).parent / "test_reconciliation_status.json"),
)
os.environ.setdefault("LUMINA_JWT_SECRET_KEY", "lumina_test_jwt_secret_key_min_len_32")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from lumina_launcher.core.config_manager import ConfigManager  # noqa: E402
from lumina_launcher.services.bot_config_persist import persist_bot_config  # noqa: E402


@pytest.mark.unit
def test_persist_bot_config_updates_yaml_not_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    config_path = tmp_path / "config.yaml"
    env_path.write_text("TRADE_MODE=real\nLUMINA_MODE=real\n", encoding="utf-8")
    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "sim",
                "sim": {
                    "kelly_fraction": 1.0,
                    "max_mutation_depth": "radical",
                    "aggressive_evolution": True,
                    "approval_required": False,
                },
                "real": {
                    "kelly_fraction": 0.25,
                    "max_mutation_depth": "conservative",
                    "aggressive_evolution": False,
                    "approval_required": True,
                },
                "broker": {"backend": "paper"},
                "risk_controller": {"real_capital_safety_threshold_usd": 1000},
                "evolution": {"approval_required": True},
            }
        ),
        encoding="utf-8",
    )
    manager = ConfigManager(env_path, config_path)

    persist_bot_config(
        config_manager=manager,
        mode_selection="real",
        risk={
            "kelly_fraction": 0.2,
            "daily_loss_cap": -120,
            "max_total_open_risk": 200,
            "real_capital_safety_threshold_usd": 1500,
        },
        evolution={
            "approval_required": True,
            "aggressive_evolution": False,
            "max_mutation_depth": "conservative",
        },
    )

    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["mode"] == "real"
    assert saved["real"]["kelly_fraction"] == 0.2
    assert saved["real"]["max_mutation_depth"] == "conservative"
    assert saved["risk_controller"]["real_capital_safety_threshold_usd"] == 1500
    assert env_path.read_text(encoding="utf-8") == "TRADE_MODE=real\nLUMINA_MODE=real\n"


@pytest.mark.unit
def test_persist_bot_config_rejects_real_radical() -> None:
    with pytest.raises(ValueError, match="radical"):
        persist_bot_config(
            config_manager=ConfigManager(Path("/nonexistent/.env"), Path("/nonexistent/config.yaml")),
            mode_selection="real",
            risk={"kelly_fraction": 0.25, "max_total_open_risk": 150, "real_capital_safety_threshold_usd": 1000},
            evolution={
                "approval_required": True,
                "aggressive_evolution": False,
                "max_mutation_depth": "radical",
            },
        )


@pytest.mark.unit
def test_post_bot_config_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    config_path = tmp_path / "config.yaml"
    env_path.write_text("TRADE_MODE=sim\n", encoding="utf-8")
    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "sim",
                "sim": {"kelly_fraction": 1.0, "max_mutation_depth": "radical"},
                "real": {"kelly_fraction": 0.25, "max_mutation_depth": "conservative"},
                "broker": {"backend": "paper"},
                "risk_controller": {},
                "evolution": {},
            }
        ),
        encoding="utf-8",
    )

    config_manager = ConfigManager(env_path, config_path)

    monkeypatch.setattr(
        "backend.config_endpoints._services",
        lambda: (None, config_manager, None, None, None, None),
    )

    client = TestClient(app)
    response = client.post(
        "/api/config/bot",
        json={
            "mode": "sim",
            "risk": {
                "kelly_fraction": 0.8,
                "daily_loss_cap": None,
                "max_total_open_risk": 2500,
                "real_capital_safety_threshold_usd": 1200,
            },
            "evolution": {
                "approval_required": False,
                "aggressive_evolution": True,
                "max_mutation_depth": "moderate",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["defaults"]["sim"]["kelly_fraction"] == 0.8

    reject = client.post(
        "/api/config/bot",
        json={
            "mode": "real",
            "risk": {
                "kelly_fraction": 0.25,
                "max_total_open_risk": 150,
                "real_capital_safety_threshold_usd": 1000,
            },
            "evolution": {
                "approval_required": True,
                "aggressive_evolution": False,
                "max_mutation_depth": "radical",
            },
        },
    )
    assert reject.status_code == 422


@pytest.mark.unit
def test_seal_without_loss_floor_does_not_write_a_boolean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    config_path = tmp_path / "config.yaml"
    env_path.write_text("TRADE_MODE=sim\n", encoding="utf-8")
    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "sim",
                "sim": {"kelly_fraction": 1.0, "daily_loss_cap": None, "max_total_open_risk": 3000},
                "real": {"kelly_fraction": 0.25},
                "broker": {"backend": "paper"},
                "risk_controller": {},
                "evolution": {},
            }
        ),
        encoding="utf-8",
    )
    config_manager = ConfigManager(env_path, config_path)
    monkeypatch.setattr(
        "backend.config_endpoints._services",
        lambda: (None, config_manager, None, None, None, None),
    )
    monkeypatch.setattr("backend.config_endpoints._workspace_root", lambda: tmp_path)
    client = TestClient(app)
    response = client.post(
        "/api/config/bot",
        json={
            "mode": "sim",
            "seal_sim_envelope": True,
            "risk": {
                "kelly_fraction": 0.5,
                "daily_loss_cap": None,
                "max_total_open_risk": 3000,
            },
            "evolution": {
                "approval_required": True,
                "aggressive_evolution": False,
                "max_mutation_depth": "conservative",
            },
        },
    )
    assert response.status_code == 422
    assert not (tmp_path / "state" / "lumina_sim_envelope_sealed.json").is_file()
    saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert saved["sim"].get("daily_loss_cap") is None


@pytest.mark.unit
def test_seal_with_floor_writes_numeric_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    config_path = tmp_path / "config.yaml"
    env_path.write_text("TRADE_MODE=sim\n", encoding="utf-8")
    config_path.write_text(
        yaml.safe_dump(
            {
                "mode": "sim",
                "sim": {"kelly_fraction": 1.0, "max_total_open_risk": 3000},
                "real": {"kelly_fraction": 0.25},
                "broker": {"backend": "paper"},
                "risk_controller": {},
                "evolution": {},
            }
        ),
        encoding="utf-8",
    )
    config_manager = ConfigManager(env_path, config_path)
    monkeypatch.setattr(
        "backend.config_endpoints._services",
        lambda: (None, config_manager, None, None, None, None),
    )
    monkeypatch.setattr("backend.config_endpoints._workspace_root", lambda: tmp_path)
    client = TestClient(app)
    response = client.post(
        "/api/config/bot",
        json={
            "mode": "sim",
            "seal_sim_envelope": True,
            "risk": {
                "kelly_fraction": 0.5,
                "daily_loss_cap": -150,
                "max_total_open_risk": 3000,
            },
            "evolution": {
                "approval_required": True,
                "aggressive_evolution": False,
                "max_mutation_depth": "conservative",
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["playground_envelope_sealed"] is True
    assert body["daily_loss_cap"] == -150
    seal = json.loads((tmp_path / "state" / "lumina_sim_envelope_sealed.json").read_text(encoding="utf-8"))
    assert seal["daily_loss_cap"] == -150.0
    assert seal["max_total_open_risk"] == 3000.0
    assert seal["sealed"] is True


@pytest.mark.unit
def test_boolean_writer_does_not_replace_a_numeric_seal(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.envelope import envelope_sealed_for_pass, write_operator_seal
    from lumina_launcher.services.setup_persist_sim import write_sim_envelope_sealed

    write_operator_seal(
        tmp_path,
        daily_loss_cap=-150.0,
        max_total_open_risk=3000.0,
        source="telegram",
    )
    write_sim_envelope_sealed(tmp_path, sealed=True, source="bot_config_seal")
    raw = json.loads((tmp_path / "state" / "lumina_sim_envelope_sealed.json").read_text(encoding="utf-8"))
    assert raw["daily_loss_cap"] == -150.0
    assert raw["source"] == "telegram"
    assert envelope_sealed_for_pass(tmp_path) is True
