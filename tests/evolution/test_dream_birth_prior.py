from __future__ import annotations

import json

import pytest

from lumina_core.evolution.dream_engine import enrich_metrics_with_birth_prior, run_dream_batch


@pytest.mark.unit
def test_dream_batch_reads_birth_regime_prior(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    prior = {
        "regimes_covered": ["TREND_UP", "TREND_DOWN", "NEUTRAL"],
        "holdout_days": 10,
    }
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "birth_regime_prior.json").write_text(json.dumps(prior), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    metrics = enrich_metrics_with_birth_prior({"account_equity": 50_000.0, "net_pnl": 100.0})
    assert "birth_regime_prior" in metrics

    report = run_dream_batch(
        metrics,
        dream_count=200,
        horizon_days=5,
        seed=42,
        drawdown_limit_ratio=0.02,
    )
    assert any("birth_prior_regimes" in hint for hint in report.rule_hints)


@pytest.mark.unit
def test_dream_merge_nudges_sparse_birth_prior(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.evolution.dream_engine import merge_dream_hyperparam_nudges

    monkeypatch.setattr(
        "lumina_core.evolution.dream_engine.dream_risk_nudge_settings",
        lambda: (True, frozenset({"sim", "paper"})),
    )
    nudged = merge_dream_hyperparam_nudges(
        {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0},
        {"enabled": True, "breach_rate": 0.05, "rule_hints": []},
        evolution_mode="sim",
        birth_regime_prior={"regimes_covered": ["TREND_UP", "NEUTRAL"]},
    )
    assert nudged["_nudged"] is True
    assert nudged["max_risk_percent"] < 1.0
    assert nudged["drawdown_kill_percent"] < 8.0
