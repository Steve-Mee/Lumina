from __future__ import annotations

from lumina_core.engine.rl_guardrails import RLGuardrailLayer


def test_rl_guardrail_bounds_qty_and_stop() -> None:
    layer = RLGuardrailLayer()
    safe, shadow = layer.apply(
        rl_action={"signal": 1, "qty_pct": 9.0, "stop_mult": 9.0},
        baseline_signal="HOLD",
        regime="VOLATILE",
        shadow_state={},
    )

    assert safe["qty_pct"] <= 1.0
    assert safe["stop_mult"] <= 1.35
    assert shadow["last_meta"]["kill_triggered"] is False


def test_rl_guardrail_kills_after_repeated_divergence() -> None:
    layer = RLGuardrailLayer(max_divergence_streak=2)
    shadow = {}

    safe1, shadow = layer.apply(
        rl_action={"signal": 2, "qty_pct": 1.0, "stop_mult": 1.0},
        baseline_signal="BUY",
        regime="NEUTRAL",
        shadow_state=shadow,
    )
    safe2, shadow = layer.apply(
        rl_action={"signal": 2, "qty_pct": 1.0, "stop_mult": 1.0},
        baseline_signal="BUY",
        regime="NEUTRAL",
        shadow_state=shadow,
    )

    assert safe1["signal"] == 2
    assert safe2["signal"] == 0
    assert shadow["last_meta"]["kill_triggered"] is True
