from contextlib import nullcontext
from types import SimpleNamespace

import pandas as pd

from lumina_core.engine.fast_path_engine import FastPathEngine
from lumina_core.engine.analysis_service import HumanAnalysisService


def test_fast_path_run_adds_swarm_regime_context():
    class SwarmSpy:
        def __init__(self):
            self.calls = 0

        def run_swarm_cycle(self):
            self.calls += 1
            return {"global_regime": "TRENDING", "allocation": {"MES JUN26": 1.0}}

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-04 09:30", periods=80, freq="min"),
            "open": [5000.0 + i for i in range(80)],
            "high": [5001.0 + i for i in range(80)],
            "low": [4999.0 + i for i in range(80)],
            "close": [5000.5 + i for i in range(80)],
            "volume": [1000] * 80,
        }
    )
    swarm = SwarmSpy()
    engine = SimpleNamespace(
        local_engine=None,
        logger=SimpleNamespace(info=lambda *_a, **_k: None, debug=lambda *_a, **_k: None),
        market_data=SimpleNamespace(get_tape_snapshot=lambda: {"bid_ask_imbalance": 1.2, "cumulative_delta_10": 15.0}),
        config=SimpleNamespace(regime_risk_multipliers={"TRENDING": 1.4, "NEUTRAL": 0.9}),
        swarm=swarm,
    )

    result = FastPathEngine(engine=engine).run(df, 5079.5, "TRENDING")  # type: ignore[arg-type]

    assert swarm.calls == 1
    assert result["swarm_regime"] == "TRENDING"
    assert result["swarm_info"]["global_regime"] == "TRENDING"


def test_deep_analysis_writes_swarm_regime_into_dream_state():
    class SwarmSpy:
        def __init__(self):
            self.calls = 0

        def run_swarm_cycle(self):
            self.calls += 1
            return {"global_regime": "BREAKOUT", "allocation": {"MES JUN26": 1.0}}

    recorded_updates = []
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-04-04 09:30", periods=120, freq="min"),
            "open": [5000.0 + i * 0.5 for i in range(120)],
            "high": [5001.0 + i * 0.5 for i in range(120)],
            "low": [4999.0 + i * 0.5 for i in range(120)],
            "close": [5000.5 + i * 0.5 for i in range(120)],
            "volume": [1000] * 120,
        }
    )

    app = SimpleNamespace(
        logger=SimpleNamespace(
            warning=lambda *_a, **_k: None,
            info=lambda *_a, **_k: None,
            error=lambda *_a, **_k: None,
            debug=lambda *_a, **_k: None,
        ),
        run_async_safely=lambda value: value,
        multi_agent_consensus=lambda *_a, **_k: {"signal": "BUY", "confidence": 0.81, "reason": "ok"},
        retrieve_relevant_experiences=lambda *_a, **_k: [],
        meta_reasoning_and_counterfactuals=lambda *_a, **_k: {"meta_reasoning": "meta"},
        update_world_model=lambda *_a, **_k: {"macro": {"vix": 1.0}},
        detect_market_structure=lambda _df: {},
        generate_multi_tf_chart=lambda: None,
        is_significant_event=lambda *_a, **_k: True,
        get_mtf_snapshots=lambda: "mtf",
        generate_price_action_summary=lambda: "pa-summary",
    )

    engine = SimpleNamespace(
        app=app,
        live_data_lock=nullcontext(),
        ohlc_1min=df,
        fast_path=SimpleNamespace(run=lambda *_a, **_k: {"used_llm": True, "swarm_regime": "BREAKOUT"}),
        config=SimpleNamespace(instrument="MES JUN26"),
        AI_DRAWN_FIBS={},
        cost_tracker={"today": 0.0},
        emotional_twin=None,
        swarm=SwarmSpy(),
        set_current_dream_fields=lambda updates: recorded_updates.append(dict(updates)),
        get_current_dream_snapshot=lambda: {"signal": "BUY", "confidence": 0.81},
    )

    service = HumanAnalysisService(engine=engine, ppo_trainer=object())  # type: ignore[arg-type]
    service.deep_analysis(5050.0, "TRENDING", "mtf", "pa-summary")

    assert engine.swarm.calls >= 1
    assert any(update.get("swarm_regime") == "BREAKOUT" for update in recorded_updates)
