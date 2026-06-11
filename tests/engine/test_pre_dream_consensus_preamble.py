"""Tests for PreDreamConsensusPreambleService (D2 sub-slice 23)."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lumina_core.engine.pre_dream_consensus_preamble import PreDreamConsensusPreambleService


def _base_app(*, chart: str | None = "chart123") -> SimpleNamespace:
    async def _consensus(*_a, **_k):
        return {"signal": "BUY", "confidence": 0.8}

    async def _meta(*_a, **_k):
        return {"meta_reasoning": "meta", "meta_score": 0.6, "counterfactuals": []}

    return SimpleNamespace(
        np=np,
        pnl_history=[1.0, -1.0, 2.0] * 6,
        calculate_dynamic_confluence=lambda _r, _w: 0.7,
        get_mtf_snapshots=lambda: "mtf",
        detect_swing_and_fibs=lambda: (None, None, {}),
        generate_price_action_summary=lambda: "pa" * 20,
        generate_multi_tf_chart=lambda: chart,
        update_live_chart=lambda *_a, **_k: None,
        multi_agent_consensus=_consensus,
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=_meta,
        update_world_model=lambda *_a, **_k: {
            "macro": {"vix": 1.0, "dxy": 1.0, "ten_year_yield": 1.0},
            "micro": {"regime": "TRENDING", "orderflow_bias": "NEUTRAL"},
        },
        blackboard=SimpleNamespace(add_proposal=lambda **k: None),
        logger=SimpleNamespace(info=lambda *_a, **_k: None),
    )


@pytest.mark.unit
def test_chart_null_should_continue():
    app = _base_app(chart=None)
    result = PreDreamConsensusPreambleService(app=app).run_preamble(
        price=5000.0,
        df=pd.DataFrame({"close": [5000.0]}),
        regime="TRENDING",
        structure={},
        rl_signal="HOLD",
        rl_action=None,
    )
    assert result.should_continue is True
    assert result.cycle_decision_context_id is None


@pytest.mark.unit
def test_preamble_success_emits_ctx_and_consensus():
    app = _base_app()
    result = PreDreamConsensusPreambleService(app=app).run_preamble(
        price=5000.0,
        df=pd.DataFrame({"close": [5000.0]}),
        regime="TRENDING",
        structure={},
        rl_signal="BUY",
        rl_action={"qty_pct": 0.5, "stop_mult": 1.2, "target_mult": 1.1, "signal": 1},
    )
    assert result.should_continue is False
    assert result.consensus is not None
    assert result.meta is not None
    assert result.cycle_decision_context_id is not None
    assert result.cycle_decision_context_id.startswith("dream_cycle:")
    assert "RL signal BUY" in (result.rl_context or "")
    assert result.chart_base64 == "chart123"
    assert result.min_conf == 0.7
    print("MANUAL_SMOKE_SUB23_PREAMBLE_SUCCESS")


@pytest.mark.unit
def test_rl_context_hold_when_no_action():
    app = _base_app()
    result = PreDreamConsensusPreambleService(app=app).run_preamble(
        price=5000.0,
        df=pd.DataFrame({"close": [5000.0]}),
        regime="TRENDING",
        structure={},
        rl_signal="HOLD",
        rl_action=None,
    )
    assert result.rl_context == "RL signal HOLD | qty 1.00 | stop x1.00 | target x1.00"
