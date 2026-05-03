from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.self_evolution_meta_agent import should_run_multi_gen_nightly
from lumina_core.evolution.dream_engine import (
    DreamReport,
    dream_engine_config,
    dream_policy_alignment_bonus,
    enrich_nightly_report_with_dream,
    merge_dream_hyperparam_nudges,
    run_dream_batch,
)
from lumina_core.evolution.lumina_bible import LuminaBible


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


def test_should_run_multi_gen_nightly_respects_dry_run_and_mode() -> None:
    assert should_run_multi_gen_nightly(mutation_allowed=True, dry_run=True, mode_key="sim")
    assert should_run_multi_gen_nightly(mutation_allowed=True, dry_run=True, mode_key="paper")
    assert not should_run_multi_gen_nightly(mutation_allowed=True, dry_run=True, mode_key="real")
    assert should_run_multi_gen_nightly(mutation_allowed=True, dry_run=False, mode_key="real")
    assert not should_run_multi_gen_nightly(mutation_allowed=False, dry_run=True, mode_key="sim")


def test_append_dream_rule_hint_writes_entry(tmp_path: Path) -> None:
    p = tmp_path / "bible.jsonl"
    bible = LuminaBible(path=p)
    ent = bible.append_dream_rule_hint(
        hint="strengthen_drawdown_kill_in_whatif_tail",
        generation=0,
        breach_rate=0.2,
    )
    assert ent is not None
    assert ent.entry_type == "dream_rule_hint"
    text = p.read_text(encoding="utf-8")
    assert "strengthen_drawdown_kill" in text
    assert "breach_rate=" in text
    assert (
        bible.append_dream_rule_hint(
            hint="strengthen_drawdown_kill_in_whatif_tail",
            generation=1,
            breach_rate=0.2,
        )
        is None
    )


def test_enrich_nightly_report_merges_dream() -> None:
    base = {"net_pnl": 1.0, "account_equity": 10_000.0}
    dream = {
        "enabled": True,
        "breach_rate": 0.1,
        "worst_dd_ratio": 0.05,
        "median_terminal_equity_delta": -0.01,
        "rule_hints": ["a"],
        "dream_count": 100,
    }
    m = enrich_nightly_report_with_dream(base, dream)
    assert m["net_pnl"] == 1.0
    assert m["dream_engine"]["breach_rate"] == 0.1
    assert m["dream_engine"]["rule_hints"] == ["a"]


def test_dream_policy_alignment_bonus() -> None:
    de = {
        "breach_rate": 0.2,
        "rule_hints": ["strengthen_drawdown_kill_in_whatif_tail"],
    }
    b = dream_policy_alignment_bonus('{"prompt_tweak": "tighten drawdown kill when stressed"}', de)
    assert b > 0.0
    b2 = dream_policy_alignment_bonus('{"prompt_tweak": "yolo all in"}', de)
    assert b2 < b


def test_merge_dream_hyperparam_nudges_sim_tightens() -> None:
    base = {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0}
    dream = {
        "enabled": True,
        "breach_rate": 0.2,
        "rule_hints": ["strengthen_drawdown_kill_in_whatif_tail", "bias_regime_gates_toward_defensive"],
    }
    out = merge_dream_hyperparam_nudges(base, dream, evolution_mode="sim")
    assert out["_nudged"] is True
    assert float(out["max_risk_percent"]) < 1.0
    assert float(out["drawdown_kill_percent"]) < 8.0


def test_merge_dream_hyperparam_nudges_skips_real_by_default() -> None:
    base = {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0}
    dream = {
        "enabled": True,
        "breach_rate": 0.3,
        "rule_hints": ["flash_drawdown_escape_and_size_cap"],
    }
    out = merge_dream_hyperparam_nudges(base, dream, evolution_mode="real")
    assert out["_nudged"] is False
    assert float(out["max_risk_percent"]) == 1.0
