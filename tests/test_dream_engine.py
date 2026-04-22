from __future__ import annotations

from lumina_core.evolution.dream_engine import DreamReport, dream_engine_config, run_dream_batch


def test_run_dream_batch_returns_stats() -> None:
    r = run_dream_batch(
        {"net_pnl": 200.0, "max_drawdown": 400.0, "sharpe": 0.5, "account_equity": 50_000.0},
        dream_count=500,
        horizon_days=5,
        seed=42,
        drawdown_limit_ratio=0.02,
    )
    assert isinstance(r, DreamReport)
    assert r.dream_count == 500
    assert 0.0 <= r.breach_rate <= 1.0
    assert r.worst_dd_ratio >= 0.0


def test_dream_engine_config_bounds() -> None:
    enabled, n, h, ddr = dream_engine_config()
    assert isinstance(enabled, bool)
    assert 200 <= n <= 50_000
    assert 1 <= h <= 60
    assert 0.005 <= ddr <= 0.25
