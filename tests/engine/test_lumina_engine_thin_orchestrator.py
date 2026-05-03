from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.lumina_engine import LuminaEngine


def _build_config(tmp_path) -> EngineConfig:
    return EngineConfig(
        state_file=tmp_path / "state.json",
        thought_log=tmp_path / "thought_log.jsonl",
        bible_file=tmp_path / "bible.json",
        live_jsonl=tmp_path / "live_stream.jsonl",
    )


@dataclass(slots=True)
class _FakeExecutionService:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def apply_rl_live_decision(
        self,
        *,
        action_payload: dict[str, Any],
        current_price: float,
        regime: str,
        confidence_threshold: float,
    ) -> bool:
        self.calls.append(
            {
                "action_payload": action_payload,
                "current_price": current_price,
                "regime": regime,
                "confidence_threshold": confidence_threshold,
            }
        )
        return True


@pytest.mark.unit
def test_lumina_engine_orchestrates_injected_execution_service(tmp_path) -> None:
    # gegeven
    cfg = _build_config(tmp_path)
    execution = _FakeExecutionService()
    engine = LuminaEngine(config=cfg, execution_service=execution)

    # wanneer
    approved = engine.apply_rl_live_decision({"signal": "BUY"}, current_price=5000.0, regime="TRENDING")

    # dan
    assert approved is True
    assert len(execution.calls) == 1
    assert execution.calls[0]["confidence_threshold"] == pytest.approx(0.78, rel=0.0, abs=1e-9)


@dataclass(slots=True)
class _FakeRiskOrchestrator:
    initialized: bool = False
    qty_to_return: int = 3
    calls: list[dict[str, Any]] = field(default_factory=list)
    session_guard: Any = None
    risk_controller: Any = None
    risk_policy: Any = None
    final_arbitration: Any = object()
    mode_risk_profile: dict[str, float] = field(default_factory=lambda: {"real_kelly_fraction": 0.2})
    dynamic_kelly_estimator: Any = object()

    def initialize(self) -> None:
        self.initialized = True

    def calculate_adaptive_risk_and_qty(
        self,
        price: float,
        regime: str,
        stop_price: float,
        confidence: float | None = None,
    ) -> int:
        self.calls.append(
            {
                "price": price,
                "regime": regime,
                "stop_price": stop_price,
                "confidence": confidence,
            }
        )
        return self.qty_to_return


@pytest.mark.unit
def test_lumina_engine_orchestrates_injected_risk_orchestrator(tmp_path) -> None:
    # gegeven
    cfg = _build_config(tmp_path)
    risk_orchestrator = _FakeRiskOrchestrator()
    engine = LuminaEngine(config=cfg, risk_orchestrator=risk_orchestrator)

    # wanneer
    qty = engine.calculate_adaptive_risk_and_qty(
        price=5000.0,
        regime="TRENDING",
        stop_price=4990.0,
        confidence=0.85,
    )

    # dan
    assert risk_orchestrator.initialized is True
    assert qty == 3
    assert len(risk_orchestrator.calls) == 1
    assert risk_orchestrator.calls[0]["regime"] == "TRENDING"


@pytest.mark.unit
def test_lumina_engine_orchestrates_injected_dream_state_manager(tmp_path) -> None:
    # gegeven
    cfg = _build_config(tmp_path)
    updates: list[dict[str, Any]] = []
    fake_manager = SimpleNamespace(
        set_fields=lambda payload: updates.append(payload),
        set_value=lambda key, value: updates.append({key: value}),
        snapshot=lambda: {"signal": "BUY"},
    )
    engine = LuminaEngine(config=cfg, dream_state_manager=fake_manager)

    # wanneer
    engine.set_current_dream_fields({"signal": "SELL"})
    engine.set_current_dream_value("confidence", 0.9)
    snapshot = engine.get_current_dream_snapshot()

    # dan
    assert updates[0] == {"signal": "SELL"}
    assert updates[1] == {"confidence": 0.9}
    assert snapshot["signal"] == "BUY"
