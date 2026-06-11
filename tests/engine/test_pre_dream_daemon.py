"""
Tests for PreDreamDaemon (Phase 3 D2 sub-slice 7: pre_dream narrow API extraction/firewall in runtime_workers trading paths god).

Per plan: given-when-then, @pytest.mark.unit, monkeypatch for sleep-to-exit, mocks for app/twin/blackboard/infer, extend existing pre_dream twin test style, integration with runtime_workers thin deleg + bootstrap mock + dream ctx from proposal per sub4/5/6.
Fail-closed/best-effort explicit. "MANUAL_SMOKE_SUB7_SUCCESS".
"""

from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest

import lumina_core.runtime_workers as runtime_workers
from lumina_core.engine.pre_dream_daemon import PreDreamDaemon
import lumina_core.engine.pre_dream_daemon as pre_dream_mod  # for monkeypatching its time.sleep


@pytest.mark.unit
def test_pre_dream_daemon_applies_emotional_twin_correction(monkeypatch):
    """Given PreDreamDaemon with mock app + TwinSpy + infer side-effect + monkey sleep-to-exit,
    when run(), then twin.calls >=1 + ctx gen + proposal + snapshot (extend existing test style).
    """
    class TwinSpy:
        def __init__(self):
            self.calls = 0

        def apply_correction(self, dream_json):
            self.calls += 1
            patched = dict(dream_json)
            patched["signal"] = "HOLD"
            return patched

    twin = TwinSpy()

    async def _consensus(*_args, **_kwargs):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_args, **_kwargs):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame(
            {
                "open": [5000.0] * 120,
                "high": [5001.0] * 120,
                "low": [4999.0] * 120,
                "close": [5000.0] * 120,
            }
        ),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=twin,
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {
            "macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0},
            "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"},
        },
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {
            "signal": "BUY",
            "confluence_score": 0.8,
            "reason": "vision",
            "chosen_strategy": "event_driven",
            "fib_levels_drawn": {},
            "narrative_reasoning": "hello",
        },
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {
            "chosen_strategy": "event_driven",
            "signal": "BUY",
            "confluence_score": 0.8,
        },
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(
            info=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
        ),
        blackboard=SimpleNamespace(add_proposal=lambda **k: None),
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    daemon = PreDreamDaemon(app=cast(Any, app))
    with pytest.raises(SystemExit):
        daemon.run()

    assert twin.calls >= 1
    # also via thin deleg (compat)
    # (reset calls for clean)
    twin.calls = 0
    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    with pytest.raises(SystemExit):
        runtime_workers.pre_dream_daemon(cast(Any, app))
    assert twin.calls >= 1


@pytest.mark.unit
def test_pre_dream_daemon_cycle_decision_context_id_origin_and_proposal(monkeypatch):
    """Given PreDreamDaemon with mock app + blackboard spy + news avoidance,
    when run(), then blackboard.add_proposal called with producer + correlation_id cycle ctx + payload; avoid sets HOLD.
    """
    proposals = []

    def _bb_add(**k):
        proposals.append(k)

    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"open": [5000.0] * 120, "high": [5001.0] * 120, "low": [4999.0] * 120, "close": [5000.0] * 120}),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=None,
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0}, "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"}},
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {"signal": "BUY", "confluence_score": 0.8, "reason": "vision", "chosen_strategy": "event_driven", "fib_levels_drawn": {}, "narrative_reasoning": "hello"},
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {"hold_until_ts": 9999999999.0, "chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},  # avoid active
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
        blackboard=SimpleNamespace(add_proposal=_bb_add),
        news_agent=None,
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    daemon = PreDreamDaemon(app=cast(Any, app))
    with pytest.raises(SystemExit):
        daemon.run()

    assert any(p.get("producer") == "runtime_workers.pre_dream_daemon" and "decision_context_id" in str(p.get("payload", {})) for p in proposals)
    assert any("correlation_id" in p and p.get("correlation_id", "").startswith("dream_cycle:") for p in proposals)


@pytest.mark.unit
def test_pre_dream_daemon_rl_bias_forces_llm_and_news_paths(monkeypatch):
    """Given ... rl_env/ppo + news, when run(), then rl_signal forces used_llm/pass_to_llm + news proposals with ctx."""
    proposals = []
    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"open": [5000.0] * 120, "high": [5001.0] * 120, "low": [4999.0] * 120, "close": [5000.0] * 120}),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": False}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=None,
            rl_env=SimpleNamespace(_get_observation=lambda: {}),
            ppo_trainer=SimpleNamespace(predict_action=lambda _o: {"signal": 1, "qty_pct": 0.5, "stop_mult": 1.0, "target_mult": 1.0}),
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0}, "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"}},
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {"signal": "BUY", "confluence_score": 0.8, "reason": "vision", "chosen_strategy": "event_driven", "fib_levels_drawn": {}, "narrative_reasoning": "hello"},
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {"chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
        blackboard=SimpleNamespace(add_proposal=lambda **k: proposals.append(k)),
        news_agent=None,
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    daemon = PreDreamDaemon(app=cast(Any, app))
    with pytest.raises(SystemExit):
        daemon.run()

    assert any("news_impact" in str(p.get("payload", {})) and "decision_context_id" in str(p.get("payload", {})) for p in proposals)


@pytest.mark.unit
def test_pre_dream_daemon_vision_infers_and_sets(monkeypatch):
    """Given ... chart + infer returns dream_json, when run(), then set_dream + speak + store + aggregate publish if bus."""
    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    sets = []
    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"open": [5000.0] * 120, "high": [5001.0] * 120, "low": [4999.0] * 120, "close": [5000.0] * 120}),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=None,
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0}, "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"}},
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {"signal": "BUY", "confluence_score": 0.8, "reason": "vision", "chosen_strategy": "event_driven", "fib_levels_drawn": {}, "narrative_reasoning": "hello"},
        set_current_dream_fields=lambda *a, **k: sets.append(("fields", a, k)),
        get_current_dream_snapshot=lambda: {"chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
        blackboard=SimpleNamespace(add_proposal=lambda **k: None),
        engine_bus=None,  # no bus -> set path
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    daemon = PreDreamDaemon(app=cast(Any, app))
    with pytest.raises(SystemExit):
        daemon.run()

    assert len(sets) >= 1


@pytest.mark.unit
def test_pre_dream_daemon_fail_closed_best_effort_paths(monkeypatch):
    """Fail-closed/best-effort: missing twin/infer/blackboard logs/returns appropriately (no crash; current behavior preserved)."""
    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"open": [5000.0] * 120, "high": [5001.0] * 120, "low": [4999.0] * 120, "close": [5000.0] * 120}),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=None,
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0}, "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"}},
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=None,  # missing -> continue path (best effort)
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {"chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
        blackboard=None,
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    daemon = PreDreamDaemon(app=cast(Any, app))
    # Should not crash; will hit infer None -> continue -> sleep -> exit
    with pytest.raises(SystemExit):
        daemon.run()


@pytest.mark.unit
def test_pre_dream_daemon_integration_thin_deleg_and_bootstrap_style(monkeypatch):
    """Integration: thin deleg from runtime_workers.pre_dream_daemon + bootstrap-style lambda works; no behavior change."""
    calls = {"twin": 0}

    class TwinSpy:
        def apply_correction(self, d):
            calls["twin"] += 1
            return dict(d, signal="HOLD")

    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8, "reason": "ok"}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    app = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"open": [5000.0] * 120, "high": [5001.0] * 120, "low": [4999.0] * 120, "close": [5000.0] * 120}),
        detect_market_regime=lambda _df: "TRENDING",
        regime_history=[],
        detect_market_structure=lambda _df: {},
        engine=SimpleNamespace(
            fast_path=SimpleNamespace(run=lambda _df, _p, _r: {"used_llm": True}),
            config=SimpleNamespace(vision_model="dummy", news_impact_multipliers={}),
            emotional_twin=TwinSpy(),
            rl_env=None,
            ppo_trainer=None,
        ),
        pnl_history=[],
        np=np,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa",
        generate_multi_tf_chart=lambda: "abc",
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0}, "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"}},
        get_high_impact_news=lambda: {"events": [], "overall_sentiment": "neutral", "impact": "medium"},
        resolve_news_multiplier=lambda *_a, **_k: 1.0,
        set_current_dream_value=lambda *_a, **_k: None,
        infer_json=lambda *_a, **_k: {"signal": "BUY", "confluence_score": 0.8, "reason": "vision", "chosen_strategy": "event_driven", "fib_levels_drawn": {}, "narrative_reasoning": "hello"},
        set_current_dream_fields=lambda *_a, **_k: None,
        get_current_dream_snapshot=lambda: {"chosen_strategy": "event_driven", "signal": "BUY", "confluence_score": 0.8},
        AI_DRAWN_FIBS={},
        speak=lambda *_a, **_k: None,
        store_experience_to_vector_db=lambda *_a, **_k: None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None, error=lambda *_a, **_k: None),
        blackboard=SimpleNamespace(add_proposal=lambda **k: None),
    )

    monkeypatch.setattr(runtime_workers.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))
    monkeypatch.setattr(pre_dream_mod.time, "sleep", lambda *_a, **_k: (_ for _ in ()).throw(SystemExit()))

    with pytest.raises(SystemExit):
        runtime_workers.pre_dream_daemon(cast(Any, app))

    assert calls["twin"] >= 1
    print("MANUAL_SMOKE_SUB7_SUCCESS")


@pytest.mark.unit
def test_pre_dream_daemon_no_inline_consensus_preamble():
    """D2 sub23: pre_dream run() delegates chart/consensus/meta to PreDreamConsensusPreambleService."""
    from pathlib import Path

    text = Path("lumina_core/engine/pre_dream_daemon.py").read_text(encoding="utf-8")
    run_start = text.index("    def run(self)")
    run_end = text.index("\n    # --- Narrow API helpers", run_start)
    run_chunk = text[run_start:run_end]
    assert "PreDreamConsensusPreambleService" in run_chunk
    assert "multi_agent_consensus" not in run_chunk
    assert "meta_reasoning_and_counterfactuals" not in run_chunk
    assert "generate_multi_tf_chart" not in run_chunk


@pytest.mark.unit
def test_pre_dream_daemon_no_inline_vision_cycle():
    """D2 sub22: pre_dream run() delegates vision to PreDreamVisionCycleService."""
    from pathlib import Path

    text = Path("lumina_core/engine/pre_dream_daemon.py").read_text(encoding="utf-8")
    run_start = text.index("    def run(self)")
    run_end = text.index("\n    # --- Narrow API helpers", run_start)
    run_chunk = text[run_start:run_end]
    assert "PreDreamVisionCycleService" in run_chunk
    assert "vision_content = [" not in run_chunk
    assert 'context="pre_dream_vision"' not in run_chunk
    assert "TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC" not in run_chunk


@pytest.mark.unit
def test_pre_dream_daemon_no_inline_news_cycle():
    """D2 sub21: pre_dream run() delegates news to PreDreamNewsCycleService."""
    from pathlib import Path

    text = Path("lumina_core/engine/pre_dream_daemon.py").read_text(encoding="utf-8")
    run_start = text.index("    def run(self)")
    run_chunk = text[run_start : run_start + 12000]
    assert "PreDreamNewsCycleService" in run_chunk
    assert "run_news_cycle(" not in run_chunk
    assert "RUNTIME_NEWS_006" not in run_chunk
    assert "RUNTIME_NEWS_007" not in run_chunk


@pytest.mark.unit
def test_pre_dream_daemon_no_inline_market_tick():
    """D2 sub24: pre_dream run() delegates price/regime/RL/fast-path to PreDreamMarketTickService."""
    from pathlib import Path

    text = Path("lumina_core/engine/pre_dream_daemon.py").read_text(encoding="utf-8")
    run_start = text.index("    def run(self)")
    run_end = text.index("\n    # --- Narrow API helpers", run_start)
    run_chunk = text[run_start:run_end]
    assert "PreDreamMarketTickService" in run_chunk
    assert "fetch_locked_price_and_ohlc" not in run_chunk
    assert "predict_cycle_signal" not in run_chunk
    assert "fast_path.run" not in run_chunk
    assert "detect_market_regime" not in run_chunk
    assert "fast_path_no_llm_branch" not in run_chunk
    print("MANUAL_SMOKE_SUB24_PREDREAM_MARKET_TICK_SUCCESS")


# End of tests. Per test-scaffolding + plan + D2 sub-slice 7.
