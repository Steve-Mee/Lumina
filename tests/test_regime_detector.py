from __future__ import annotations

import asyncio
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pandas as pd

from lumina_core.engine.regime_detector import RegimeDetector
from lumina_core.engine.reasoning_service import ReasoningService
from lumina_core.engine.risk_controller import HardRiskController, RiskLimits
from lumina_core.engine.self_evolution_meta_agent import SelfEvolutionMetaAgent
from lumina_core.evolution.dna_registry import DNARegistry
from lumina_core.trade_workers import check_pre_trade_risk


def _build_frame(
    closes: list[float],
    *,
    start: str = "2026-04-06T14:30:00+00:00",
    volume_base: float = 1200.0,
    volume_bump: dict[int, float] | None = None,
    spread: float = 0.25,
) -> pd.DataFrame:
    volume_bump = volume_bump or {}
    rows: list[dict[str, float | str]] = []
    ts = pd.Timestamp(start)
    prev = closes[0]
    for idx, close in enumerate(closes):
        move = close - prev if idx > 0 else 0.15
        open_price = prev if idx > 0 else close - 0.15
        range_pad = max(0.2, abs(move) * 0.7 + 0.2)
        rows.append(
            {
                "timestamp": (ts + pd.Timedelta(minutes=idx)).isoformat(),
                "open": round(open_price, 4),
                "high": round(max(open_price, close) + range_pad, 4),
                "low": round(min(open_price, close) - range_pad, 4),
                "close": round(close, 4),
                "volume": float(volume_bump.get(idx, volume_base)),
                "spread": spread,
            }
        )
        prev = close
    return pd.DataFrame(rows)


def _trending_frame() -> pd.DataFrame:
    closes = [5000.0 + (idx * 0.42) + math.sin(idx / 5.0) * 0.1 for idx in range(140)]
    return _build_frame(closes, volume_base=1400.0)


def _ranging_frame() -> pd.DataFrame:
    closes = [5000.0 + math.sin(idx / 3.0) * 1.2 for idx in range(140)]
    return _build_frame(closes, volume_base=1250.0)


def _high_vol_frame() -> pd.DataFrame:
    closes = [5000.0]
    for idx in range(1, 140):
        closes.append(closes[-1] + math.sin(idx / 2.0) * 3.5 + (1.5 if idx % 4 == 0 else -1.2))
    return _build_frame(closes, volume_base=1800.0, spread=0.4)


def _news_frame() -> pd.DataFrame:
    closes = [5000.0 + math.sin(idx / 6.0) * 0.5 for idx in range(140)]
    for idx in range(132, 140):
        closes[idx] = closes[idx - 1] + 6.5
    bumps = {idx: 4200.0 for idx in range(132, 140)}
    return _build_frame(closes, volume_base=1150.0, volume_bump=bumps, spread=0.35)


def _low_liquidity_frame() -> pd.DataFrame:
    closes = [5000.0 + math.sin(idx / 9.0) * 0.4 for idx in range(140)]
    return _build_frame(
        closes,
        start="2026-04-06T02:15:00+00:00",
        volume_base=180.0,
        spread=1.0,
    )


class TestRegimeDetector:
    def test_detects_trending_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(_trending_frame(), instrument="MES JUN26", confluence_score=0.82)
        assert snapshot.label == "TRENDING"
        assert snapshot.adaptive_policy.agent_route[0] == "swing"

    def test_detects_ranging_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(_ranging_frame(), instrument="MES JUN26", confluence_score=0.61)
        assert snapshot.label == "RANGING"
        assert snapshot.adaptive_policy.risk_multiplier < 1.0

    def test_detects_high_volatility_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(_high_vol_frame(), instrument="MES JUN26", confluence_score=0.7)
        assert snapshot.label == "HIGH_VOLATILITY"
        assert snapshot.risk_state == "HIGH_RISK"

    def test_detects_news_driven_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(
            _news_frame(),
            instrument="MES JUN26",
            confluence_score=0.93,
            structure={"bos": "bullish_BOS", "choch": None, "fvg": [1]},
        )
        assert snapshot.label == "NEWS_DRIVEN"
        assert snapshot.adaptive_policy.high_risk is True

    def test_detects_rollover_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(
            _trending_frame(),
            instrument="MES JUN26",
            confluence_score=0.7,
            now=pd.Timestamp("2026-06-17T14:30:00+00:00").to_pydatetime(),
        )
        assert snapshot.label == "ROLLOVER"

    def test_detects_low_liquidity_regime(self) -> None:
        detector = RegimeDetector()
        snapshot = detector.detect(_low_liquidity_frame(), instrument="MES JUN26", confluence_score=0.55)
        assert snapshot.label == "LOW_LIQUIDITY"
        assert snapshot.adaptive_policy.fast_path_weight > 0.8


def _build_reasoning_engine(frame: pd.DataFrame) -> tuple[SimpleNamespace, HardRiskController]:
    risk = HardRiskController(
        RiskLimits(
            daily_loss_cap=-1000.0,
            max_consecutive_losses=3,
            max_open_risk_per_instrument=500.0,
            max_exposure_per_regime=2000.0,
            cooldown_after_streak=30,
            enforce_session_guard=False,
        ),
        enforce_rules=True,
    )
    app = SimpleNamespace(
        logger=SimpleNamespace(
            info=lambda *args, **kwargs: None, warning=lambda *args, **kwargs: None, error=lambda *args, **kwargs: None
        ),
        FAST_PATH_ONLY=False,
    )
    engine = SimpleNamespace(
        app=app,
        config=SimpleNamespace(
            instrument="MES JUN26",
            agent_styles={"scalper": "s", "swing": "w", "risk": "r"},
        ),
        ohlc_1min=frame,
        current_regime_snapshot={},
        risk_controller=risk,
        get_current_dream_snapshot=lambda: {"confluence_score": 0.9},
    )
    return engine, risk


def test_reasoning_service_updates_regime_snapshot_and_risk_limits() -> None:
    engine, risk = _build_reasoning_engine(_news_frame())
    detector = RegimeDetector()
    reasoning = ReasoningService(
        engine=cast(Any, engine),
        inference_engine=cast(
            Any,
            SimpleNamespace(infer_json=lambda *args, **kwargs: {"signal": "BUY", "confidence": 0.9, "reason": "ok"}),
        ),
        regime_detector=detector,
    )

    snapshot = reasoning.refresh_regime_snapshot(structure={"bos": "bullish_BOS", "fvg": [1]})
    assert snapshot.label == "NEWS_DRIVEN"
    assert engine.current_regime_snapshot["label"] == "NEWS_DRIVEN"
    assert risk.get_status()["active_limits"]["max_open_risk_per_instrument"] < 500.0


def test_reasoning_service_routes_agents_by_regime() -> None:
    engine, _ = _build_reasoning_engine(_trending_frame())
    captured_contexts: list[str] = []

    def _infer_json(_payload, *, timeout, context, max_retries):
        del timeout, max_retries
        captured_contexts.append(context)
        return {"signal": "BUY", "confidence": 0.8, "reason": "aligned"}

    reasoning = ReasoningService(
        engine=cast(Any, engine),
        inference_engine=cast(Any, SimpleNamespace(infer_json=_infer_json)),
        regime_detector=RegimeDetector(),
    )

    result = asyncio.run(
        reasoning.multi_agent_consensus(
            price=5010.0,
            mtf_data="up",
            pa_summary="trend",
            structure={"bos": True, "choch": None},
            fib_levels={"0.5": 5008.0},
        )
    )

    assert result["regime"]["label"] == "TRENDING"
    assert captured_contexts[0] == "multi_agent_swing"


def test_trade_workers_apply_tighter_limits_in_high_risk_regime() -> None:
    risk = HardRiskController(
        RiskLimits(max_open_risk_per_instrument=500.0, enforce_session_guard=False),
        enforce_rules=True,
    )
    snapshot = {
        "label": "LOW_LIQUIDITY",
        "risk_state": "HIGH_RISK",
        "adaptive_policy": {
            "risk_multiplier": 0.4,
            "cooldown_minutes": 55,
        },
    }
    app = SimpleNamespace(
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        market_regime="NEUTRAL",
    )
    engine = SimpleNamespace(
        risk_controller=risk,
        current_regime_snapshot=snapshot,
        reasoning_service=SimpleNamespace(refresh_regime_snapshot=lambda: snapshot),
        blackboard=SimpleNamespace(
            latest=lambda topic: SimpleNamespace(
                payload={"agent_id": "rl", "confidence": 0.8, "reason": "test", "signal": "BUY"}
                if str(topic).startswith("agent.")
                else {"signal": "BUY", "chosen_strategy": "rl"},
                producer="test",
                confidence=0.8,
                timestamp="2026-04-18T00:00:00+00:00",
                correlation_id="corr",
                sequence=1,
                event_hash="hash",
                prev_hash="prev-hash",
            )
        ),
        audit_log_service=SimpleNamespace(log_decision=lambda *_a, **_k: True),
        get_current_dream_snapshot=lambda: {"confidence": 0.7, "expected_value": 1.0},
        swarm=SimpleNamespace(current_symbol="MES JUN26"),
    )
    runtime = SimpleNamespace(engine=engine, logger=app.logger, market_regime="NEUTRAL")

    allowed, reason = check_pre_trade_risk(cast(Any, runtime), "MES JUN26", "NEUTRAL", 250.0)
    assert allowed is False
    assert "MAX INSTRUMENT RISK exceeded" in reason


def test_self_evolution_meta_agent_uses_regime_breakdown(tmp_path: Path) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(
            risk_profile="balanced",
            max_risk_percent=1.0,
            drawdown_kill_percent=8.0,
            agent_styles={"risk": "r"},
        ),
        regime_history=[{"label": "TRENDING"}, {"label": "RANGING"}, {"label": "NEWS_DRIVEN"}],
        emotional_twin=None,
    )
    agent = SelfEvolutionMetaAgent(
        engine=cast(Any, engine),
        valuation_engine=cast(Any, SimpleNamespace()),
        risk_controller=HardRiskController(RiskLimits(enforce_session_guard=False), enforce_rules=True),
        approval_required=True,
        runtime_mode="paper",
        log_path=tmp_path / "evolution_log.jsonl",
        dna_registry=DNARegistry(
            jsonl_path=tmp_path / "dna_registry.jsonl",
            sqlite_path=tmp_path / "dna_registry.sqlite3",
        ),
    )
    result = agent.run_nightly_evolution(
        nightly_report={
            "trades": 120,
            "wins": 64,
            "net_pnl": 920.0,
            "sharpe": 0.84,
            "regime_attribution": {
                "TRENDING": {"trades": 50, "net_pnl": 700.0, "winrate": 0.62},
                "NEWS_DRIVEN": {"trades": 20, "net_pnl": -120.0, "winrate": 0.35},
            },
        },
        dry_run=True,
    )

    assert result["meta_review"]["regime_breakdown"]["NEWS_DRIVEN"]["net_pnl"] == -120.0
    assert result["best_candidate"]["regime_focus"] == "news_driven"
    assert "meta_swarm" in result["meta_review"]
    assert "allow_promotion" in result["meta_review"]["meta_swarm"]
