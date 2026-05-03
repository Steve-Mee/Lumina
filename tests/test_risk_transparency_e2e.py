from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

from lumina_core.audit.audit_log_service import AuditLogService
from lumina_core.risk.risk_controller import HardRiskController, RiskLimits, risk_limits_from_config
from lumina_core.risk.equity_snapshot import EquitySnapshot
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC


class _AlwaysApproveArbitration:
    def check_order_intent(self, *_args, **_kwargs):
        return SimpleNamespace(status="APPROVED", reason="approved")


def _bb_event(*, topic: str, producer: str, payload: dict, confidence: float, sequence: int):
    return SimpleNamespace(
        topic=topic,
        producer=producer,
        payload=payload,
        confidence=confidence,
        timestamp="2026-04-16T10:30:00+00:00",
        correlation_id=f"corr-{sequence}",
        sequence=sequence,
        event_hash=f"hash-{sequence}",
        prev_hash=f"hash-{sequence - 1}",
    )


def _fresh_snapshot_provider(*, equity: float = 100_000.0, free_margin: float = 60_000.0):
    class _SnapshotProvider:
        def get_snapshot(self) -> EquitySnapshot:
            return EquitySnapshot(
                equity_usd=equity,
                available_margin_usd=free_margin,
                used_margin_usd=max(0.0, equity - free_margin),
                as_of_utc=datetime.now(timezone.utc),
                source="test",
                ok=True,
                reason_code="ok_live",
                ttl_seconds=30.0,
            )

    return _SnapshotProvider()


def test_e2e_real_mode_blocks_on_mc_drawdown_and_logs_decision(tmp_path: Path) -> None:
    audit_path = tmp_path / "trade_decision_audit.jsonl"
    risk_limits = RiskLimits(
        enforce_session_guard=False,
        runtime_mode="real",
        mc_drawdown_paths=1200,
        mc_drawdown_horizon_days=60,
        mc_drawdown_min_samples=20,
        mc_drawdown_threshold_pct=4.0,
        enable_mc_drawdown_enforce_real=True,
        daily_loss_cap=-10000.0,
        max_consecutive_losses=50,
    )
    risk_controller = HardRiskController(risk_limits, enforce_rules=True)
    for i in range(40):
        pnl = -140.0 if i % 2 == 0 else 35.0
        risk_controller.record_trade_result("MES", "HIGH_VOLATILITY", pnl=pnl, risk_taken=100.0)

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real", instrument="MES JUN26"),
        risk_controller=risk_controller,
        session_guard=None,
        current_regime_snapshot={
            "label": "HIGH_VOLATILITY",
            "risk_state": "HIGH_RISK",
            "adaptive_policy": {"risk_multiplier": 0.55, "cooldown_minutes": 45},
            "features": {"realized_vol_ratio": 1.95},
        },
        market_regime="HIGH_VOLATILITY",
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {
                "label": "HIGH_VOLATILITY",
                "risk_state": "HIGH_RISK",
                "adaptive_policy": {"risk_multiplier": 0.55, "cooldown_minutes": 45},
                "features": {"realized_vol_ratio": 1.95},
            }
        ),
        observability_service=SimpleNamespace(record_mode_guard_block=lambda **_kwargs: None),
        audit_log_service=AuditLogService(path=audit_path, enabled=True, fail_closed_real=True),
        blackboard=SimpleNamespace(
            latest=lambda topic: {
                "agent.rl.proposal": _bb_event(
                    topic="agent.rl.proposal",
                    producer="rl_policy",
                    payload={"signal": "BUY", "confidence": 0.81, "reason": "rl bias"},
                    confidence=0.81,
                    sequence=11,
                ),
                "agent.news.proposal": _bb_event(
                    topic="agent.news.proposal",
                    producer="news_agent",
                    payload={"signal": "HOLD", "confidence": 0.74, "reason": "event risk"},
                    confidence=0.74,
                    sequence=12,
                ),
            }.get(str(topic))
        ),
        event_bus=SimpleNamespace(
            latest=lambda topic: (
                SimpleNamespace(
                    producer="runtime_workers.pre_dream_daemon",
                    payload={"signal": "BUY", "chosen_strategy": "ppo_live_policy", "confidence": 0.86},
                    timestamp="2026-04-16T10:30:00+00:00",
                    metadata={"sequence": 13, "correlation_id": "corr-13"},
                    to_dict=lambda: {
                        "topic": TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
                        "producer": "runtime_workers.pre_dream_daemon",
                        "payload": {"signal": "BUY", "chosen_strategy": "ppo_live_policy", "confidence": 0.86},
                        "timestamp": "2026-04-16T10:30:00+00:00",
                        "metadata": {"sequence": 13, "correlation_id": "corr-13"},
                    },
                )
                if topic == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
                else None
            )
        ),
        get_current_dream_snapshot=lambda: {
            "chosen_strategy": "ppo_live_policy",
            "confidence": 0.86,
            "expected_value": -22.0,
            "reason": "high volatility pressure",
        },
        equity_snapshot_provider=_fresh_snapshot_provider(),
        account_equity=100_000.0,
        available_margin=60_000.0,
        positions_margin_used=40_000.0,
        live_position_qty=0,
        final_arbitration=_AlwaysApproveArbitration(),
    )

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="HIGH_VOLATILITY",
        proposed_risk=250.0,
        order_side="BUY",
    )

    assert allowed is False
    assert "drawdown" in reason.lower()

    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines, "Expected at least one trade decision audit event"
    risk_gate_events = [row for row in lines if str(row.get("stage")) == "policy_gate"]
    assert risk_gate_events, "Expected a policy_gate audit entry"
    risk_gate = risk_gate_events[-1]
    assert risk_gate["final_decision"] == "block"
    assert "monte_carlo" in risk_gate
    assert float(risk_gate["monte_carlo"].get("projected_max_drawdown_pct", 0.0)) > 0.0
    assert isinstance(risk_gate.get("agents_involved"), list)
    assert len(risk_gate["agents_involved"]) >= 2
    assert risk_gate["agents_involved"][0].get("topic", "").startswith("agent.")
    assert "lineage" in risk_gate["agents_involved"][0]
    assert risk_gate.get("execution_aggregate_lineage", {}).get("topic") == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC


def test_e2e_pretrade_uses_default_mc_paths_and_horizon_from_config(tmp_path: Path) -> None:
    audit_path = tmp_path / "trade_decision_audit.jsonl"
    limits = risk_limits_from_config(
        {
            "mode": "real",
            "risk_controller": {
                "enforce_session_guard": False,
                "mc_drawdown_threshold_pct": 95.0,
            },
        }
    )
    risk_controller = HardRiskController(limits, enforce_rules=True)
    for i in range(60):
        pnl = 30.0 if i % 3 else -20.0
        risk_controller.record_trade_result("MES", "TRENDING", pnl=pnl, risk_taken=100.0)

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real", instrument="MES JUN26"),
        risk_controller=risk_controller,
        session_guard=None,
        current_regime_snapshot={
            "label": "TRENDING",
            "risk_state": "NORMAL",
            "adaptive_policy": {"risk_multiplier": 1.0, "cooldown_minutes": 30},
            "features": {"realized_vol_ratio": 1.1},
        },
        market_regime="TRENDING",
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {
                "label": "TRENDING",
                "risk_state": "NORMAL",
                "adaptive_policy": {"risk_multiplier": 1.0, "cooldown_minutes": 30},
                "features": {"realized_vol_ratio": 1.1},
            }
        ),
        observability_service=SimpleNamespace(record_mode_guard_block=lambda **_kwargs: None),
        audit_log_service=AuditLogService(path=audit_path, enabled=True, fail_closed_real=True),
        blackboard=SimpleNamespace(
            latest=lambda topic: {
                "agent.rl.proposal": _bb_event(
                    topic="agent.rl.proposal",
                    producer="rl_policy",
                    payload={"signal": "BUY", "confidence": 0.8, "reason": "steady trend"},
                    confidence=0.8,
                    sequence=21,
                ),
            }.get(str(topic))
        ),
        event_bus=SimpleNamespace(
            latest=lambda topic: (
                SimpleNamespace(
                    producer="runtime_workers.pre_dream_daemon",
                    payload={"signal": "BUY", "chosen_strategy": "ppo_live_policy", "confidence": 0.8},
                    timestamp="2026-04-16T10:30:00+00:00",
                    metadata={"sequence": 22, "correlation_id": "corr-22"},
                    to_dict=lambda: {
                        "topic": TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
                        "producer": "runtime_workers.pre_dream_daemon",
                        "payload": {"signal": "BUY", "chosen_strategy": "ppo_live_policy", "confidence": 0.8},
                        "timestamp": "2026-04-16T10:30:00+00:00",
                        "metadata": {"sequence": 22, "correlation_id": "corr-22"},
                    },
                )
                if topic == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
                else None
            )
        ),
        get_current_dream_snapshot=lambda: {
            "chosen_strategy": "ppo_live_policy",
            "confidence": 0.77,
            "expected_value": 6.0,
            "reason": "default config validation",
        },
        equity_snapshot_provider=_fresh_snapshot_provider(),
        account_equity=100_000.0,
        available_margin=60_000.0,
        positions_margin_used=40_000.0,
        live_position_qty=0,
        final_arbitration=_AlwaysApproveArbitration(),
    )

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="TRENDING",
        proposed_risk=100.0,
        order_side="BUY",
    )

    assert allowed is True
    assert reason == "OK"

    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    risk_gate_events = [row for row in lines if str(row.get("stage")) == "admission_chain"]
    assert risk_gate_events, "Expected admission_chain audit event for active pre-trade path"
    risk_gate = risk_gate_events[-1]
    mc = risk_gate.get("monte_carlo", {}) if isinstance(risk_gate.get("monte_carlo", {}), dict) else {}
    assert int(float(mc.get("paths", 0.0) or 0.0)) == 10000
    assert int(float(mc.get("horizon_days", 0.0) or 0.0)) == 252
