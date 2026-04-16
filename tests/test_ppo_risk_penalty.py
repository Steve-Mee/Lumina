from __future__ import annotations

from types import SimpleNamespace

from lumina_core.ppo_trainer import PPOTrainer


def test_build_rl_config_includes_var_es_penalty_coefficients() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode="sim",
            risk_controller={
                "sim_var_penalty_coeff": 0.22,
                "sim_es_penalty_coeff": 0.33,
                "slippage_base_points": 0.2,
                "slippage_sigma": 0.7,
                "slippage_volatility_factor": 1.1,
            },
        )
    )

    trainer = PPOTrainer(engine=engine)
    cfg = trainer._build_rl_config()

    assert float(cfg.sim_var_penalty_coeff) == 0.22
    assert float(cfg.sim_es_penalty_coeff) == 0.33
    assert float(cfg.slippage_points) == 0.2
    assert float(cfg.slippage_sigma) == 0.7
    assert float(cfg.slippage_volatility_factor) == 1.1
    assert cfg.trade_mode == "sim"


def test_build_rl_config_real_mode_propagates_safety_thresholds() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode="real",
            risk_controller={
                "real_capital_safety_threshold_usd": 2500.0,
                "real_capital_safety_threshold_ratio": 0.95,
            },
        )
    )

    trainer = PPOTrainer(engine=engine)
    cfg = trainer._build_rl_config()

    assert cfg.trade_mode == "real"
    assert float(cfg.real_safety_threshold_usd) == 2500.0
    assert float(cfg.real_safety_threshold_ratio) == 0.95
