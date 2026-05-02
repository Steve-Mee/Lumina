from __future__ import annotations

import pytest
import yaml

from lumina_core.config_loader import ConfigLoader
from lumina_core.risk.risk_policy import RiskPolicy, load_risk_policy


@pytest.mark.unit
class TestRiskPolicyOverlays:
    def test_real_limits_are_stricter_than_sim(self) -> None:
        # gegeven
        cfg = {
            "mode": "real",
            "risk_controller": {
                "daily_loss_cap": -1000.0,
                "max_open_risk_per_instrument": 500.0,
                "max_total_open_risk": 3000.0,
                "max_exposure_per_regime": 2000.0,
                "kelly_fraction": 0.5,
            },
            "sim": {
                "daily_loss_cap": -1000000.0,
                "max_open_risk_per_instrument": 700.0,
                "max_total_open_risk": 5000.0,
                "max_exposure_per_regime": 3500.0,
                "kelly_fraction": 1.0,
            },
            "real": {
                "daily_loss_cap": -150.0,
                "max_open_risk_per_instrument": 75.0,
                "max_total_open_risk": 150.0,
                "max_exposure_per_regime": 100.0,
                "kelly_fraction": 0.25,
            },
        }

        # wanneer
        sim_policy = RiskPolicy.get_effective_policy(mode="sim", config=cfg)
        real_policy = RiskPolicy.get_effective_policy(mode="real", config=cfg)

        # dan
        assert abs(real_policy.daily_loss_cap) <= abs(sim_policy.daily_loss_cap)
        assert real_policy.max_open_risk_per_instrument <= sim_policy.max_open_risk_per_instrument
        assert real_policy.max_total_open_risk <= sim_policy.max_total_open_risk
        assert real_policy.max_exposure_per_regime <= sim_policy.max_exposure_per_regime
        assert real_policy.kelly_fraction <= sim_policy.kelly_fraction

    def test_instrument_override_applies_only_for_target_symbol(self) -> None:
        # gegeven
        cfg = {
            "mode": "real",
            "risk_controller": {
                "max_open_risk_per_instrument": 500.0,
                "max_total_open_risk": 3000.0,
                "max_exposure_per_regime": 2000.0,
                "daily_loss_cap": -1000.0,
            },
            "real": {
                "max_open_risk_per_instrument": 75.0,
                "max_total_open_risk": 150.0,
                "max_exposure_per_regime": 100.0,
                "daily_loss_cap": -150.0,
            },
            "risk_instrument_overrides": {
                "MES JUN26": {
                    "max_open_risk_per_instrument": 40.0,
                }
            },
        }

        # wanneer
        target = RiskPolicy.get_effective_policy(mode="real", instrument="mes jun26", config=cfg)
        other = RiskPolicy.get_effective_policy(mode="real", instrument="NQ JUN26", config=cfg)

        # dan
        assert target.max_open_risk_per_instrument == pytest.approx(40.0)
        assert other.max_open_risk_per_instrument == pytest.approx(75.0)

    def test_yaml_change_is_applied_without_process_restart(self, tmp_path, monkeypatch) -> None:
        # gegeven
        cfg_path = tmp_path / "config.yaml"
        first = {
            "mode": "real",
            "risk_controller": {
                "daily_loss_cap": -1000.0,
                "max_total_open_risk": 3000.0,
            },
            "real": {"max_total_open_risk": 150.0},
        }
        cfg_path.write_text(yaml.safe_dump(first, sort_keys=False), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        ConfigLoader.invalidate()

        # wanneer
        before = load_risk_policy(mode="real", reload_config=True)
        second = {
            "mode": "real",
            "risk_controller": {
                "daily_loss_cap": -1000.0,
                "max_total_open_risk": 3000.0,
            },
            "real": {"max_total_open_risk": 90.0},
        }
        cfg_path.write_text(yaml.safe_dump(second, sort_keys=False), encoding="utf-8")
        ConfigLoader.invalidate()
        after = load_risk_policy(mode="real", reload_config=True)

        # dan
        assert before.max_total_open_risk == pytest.approx(150.0)
        assert after.max_total_open_risk == pytest.approx(90.0)
