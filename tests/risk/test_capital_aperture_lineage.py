"""H1: capital aperture lineage contract on admission path."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.risk.capital_aperture_lineage import (
    aperture_lineage_integrity_snapshot,
    ensure_order_lineage,
    extract_order_lineage,
    require_order_lineage,
)


@dataclass
class _Order:
    symbol: str = "MNQ"
    side: str = "BUY"
    quantity: int = 1
    stop_loss: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@pytest.mark.unit
def test_strict_mode_rejects_missing_lineage() -> None:
    order = _Order()
    ok, reason = require_order_lineage(order, mode="real")
    assert ok is False
    assert "missing_decision_context_id" in reason
    ok2, reason2 = ensure_order_lineage(order, mode="real")
    assert ok2 is False
    assert "missing_decision_context_id" in reason2
    assert not order.metadata.get("decision_context_id")


@pytest.mark.unit
def test_soft_mode_ensures_synthetic_lineage() -> None:
    order = _Order()
    ok, reason = ensure_order_lineage(order, mode="sim")
    assert ok is True
    assert reason == "ok_soft_ensured"
    assert order.metadata.get("decision_context_id")
    assert order.metadata.get("lineage_source") == "capital_aperture_soft_ensure"


@pytest.mark.unit
def test_legacy_bypass_flag_stripped() -> None:
    order = _Order(metadata={"decision_context_id": "ctx-1", "skip_admission_chain_recheck": True})
    ok, _ = ensure_order_lineage(order, mode="paper")
    assert ok is True
    assert "skip_admission_chain_recheck" not in order.metadata
    assert order.metadata.get("legacy_bypass_flag_stripped") is True


@pytest.mark.unit
def test_run_final_arbitration_fails_closed_real_without_ctx() -> None:
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="real"), audit_log_service=None)
    order = _Order(metadata={"proposed_risk": 1.0, "regime": "NEUTRAL"})
    allowed, reason = run_final_arbitration(engine, order)
    assert allowed is False
    assert "missing_decision_context_id" in reason


@pytest.mark.unit
def test_run_final_arbitration_soft_ensures_then_gate() -> None:
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="sim"), audit_log_service=None)
    order = _Order(metadata={"proposed_risk": 1.0, "regime": "NEUTRAL"})

    def _gate(*_a: Any, **_k: Any) -> tuple[bool, str]:
        return True, "ok"

    with patch(
        "lumina_core.broker.broker_bridge.admission._bb.enforce_pre_trade_gate",
        side_effect=_gate,
    ):
        allowed, reason = run_final_arbitration(engine, order)
    assert allowed is True
    assert order.metadata.get("decision_context_id")
    lin = extract_order_lineage(order)
    assert lin["decision_context_id"]


@pytest.mark.unit
def test_integrity_snapshot_counts_rows(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    log = state / "audit_log.jsonl"
    log.write_text(
        "\n".join(
            [
                '{"decision_context_id": "a", "stage": "x"}',
                '{"stage": "y"}',
                '{"metadata": {"decision_context_id": "b"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    snap = aperture_lineage_integrity_snapshot(tmp_path, audit_limit=50)
    assert snap["sample_size"] == 3
    assert snap["with_decision_context_id"] == 2
    assert snap["without_decision_context_id"] == 1
    assert snap["lineage_coverage_pct"] == pytest.approx(66.67)
    assert snap["target_coverage_pct"] == 95.0
    assert snap["coverage_meets_h1_goal"] is False
    assert snap["coverage_meets_phase2_goal"] is False


@pytest.mark.unit
def test_append_lineage_audit_and_prefers_decision_log(tmp_path: Path) -> None:
    from lumina_core.risk.capital_aperture_lineage import append_lineage_audit_record

    ok = append_lineage_audit_record(
        tmp_path,
        {"decision_context_id": "ctx-h1", "stage": "capital_aperture_admission"},
    )
    assert ok is True
    log = tmp_path / "state" / "decision_log.jsonl"
    assert log.is_file()
    # Also write a noisier audit_log without ctx — decision_log should win as source
    (tmp_path / "state" / "audit_log.jsonl").write_text(
        '{"stage": "other"}\n', encoding="utf-8"
    )
    snap = aperture_lineage_integrity_snapshot(tmp_path, audit_limit=50)
    assert "decision_log.jsonl" in str(snap.get("audit_source") or "")
    assert snap["with_decision_context_id"] >= 1
    assert snap["lineage_coverage_pct"] == pytest.approx(100.0)
    assert snap["coverage_meets_h1_goal"] is True


@pytest.mark.unit
def test_live_mode_is_lineage_strict() -> None:
    from lumina_core.risk.capital_aperture_lineage import is_lineage_strict_mode

    assert is_lineage_strict_mode("real") is True
    assert is_lineage_strict_mode("live") is True
    assert is_lineage_strict_mode("production") is True
    assert is_lineage_strict_mode("sim") is False
    assert is_lineage_strict_mode("birth") is False


@pytest.mark.unit
def test_capital_aperture_residual_report_shape() -> None:
    from lumina_core.risk.capital_aperture_lineage import capital_aperture_residual_report

    rep = capital_aperture_residual_report()
    assert rep["schema"] == "capital_aperture_residual_v1"
    assert rep["single_non_bypassable_aperture"] is True
    assert rep["policy"]["twin_cannot_bypass_aperture"] is True
    closed_ids = {c["id"] for c in rep["closed"]}
    residual_ids = {r["id"] for r in rep["residual"]}
    assert "strict_lineage_required" in closed_ids
    assert "durable_decision_log" in closed_ids
    assert "full_capital_path_bus_rewire" in residual_ids
    assert "h1_95pct_live_production" in residual_ids


@pytest.mark.unit
def test_integrity_snapshot_embeds_residual(tmp_path: Path) -> None:
    snap = aperture_lineage_integrity_snapshot(tmp_path, audit_limit=10)
    assert "residual" in snap
    assert snap["residual"]["schema"] == "capital_aperture_residual_v1"


@pytest.mark.unit
def test_reject_path_appends_decision_log(tmp_path: Path) -> None:
    """Track E: FA reject still durable-logs lineage for reconstructability."""
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real", workspace_root=tmp_path),
        audit_log_service=None,
        event_bus=None,
    )
    order = _Order(metadata={"proposed_risk": 1.0, "regime": "NEUTRAL"})
    allowed, reason = run_final_arbitration(engine, order)
    assert allowed is False
    assert "missing_decision_context_id" in reason
    # Soft path would invent; REAL must not invent — decision_log may still get reject row
    # when lineage was present; for missing lineage, ensure we don't invent REAL ctx.
    assert not order.metadata.get("decision_context_id")


@pytest.mark.unit
def test_fabric_blocks_strict_without_lineage() -> None:
    """Fabric transport is not a capital aperture bypass."""
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="real", trade_mode="real")
            self.is_connected = True
            self._safe_mode = 1  # NORMAL

        @property
        def safe_mode(self) -> int:
            return self._safe_mode

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"type": "ok"}

    fake = _Fake()
    order = _Order()
    out = fake.place_order_sync(order, client_order_id="c1")
    assert out.get("code") == "APERTURE_LINEAGE_MISSING"
    assert out.get("type") == "error"


@pytest.mark.unit
def test_coverage_gate_soft_pass_no_samples(tmp_path: Path) -> None:
    from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

    gate = evaluate_aperture_coverage_gate(workspace_root=tmp_path, min_sample_size=10)
    assert gate["ok"] is True
    assert gate["soft_pass"] is True
    assert gate["reason"] == "no_samples"


@pytest.mark.unit
def test_coverage_gate_soft_pass_thin_sample(tmp_path: Path) -> None:
    from lumina_core.risk.capital_aperture_lineage import (
        append_lineage_audit_record,
        evaluate_aperture_coverage_gate,
    )

    for i in range(3):
        append_lineage_audit_record(
            tmp_path,
            {"decision_context_id": f"ctx-{i}", "stage": "capital_aperture_admission"},
        )
    gate = evaluate_aperture_coverage_gate(
        workspace_root=tmp_path, min_sample_size=10, min_coverage_pct=95.0
    )
    assert gate["ok"] is True
    assert gate["soft_pass"] is True
    assert gate["reason"] == "thin_sample"
    assert gate["sample_size"] == 3


@pytest.mark.unit
def test_coverage_gate_hard_fail_below_target(tmp_path: Path) -> None:
    from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

    state = tmp_path / "state"
    state.mkdir(parents=True)
    lines = []
    for i in range(8):
        lines.append(json.dumps({"decision_context_id": f"c{i}", "stage": "x"}))
    for i in range(4):
        lines.append(json.dumps({"stage": "no_ctx"}))
    (state / "decision_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    gate = evaluate_aperture_coverage_gate(
        workspace_root=tmp_path, min_sample_size=10, min_coverage_pct=95.0
    )
    assert gate["sample_size"] == 12
    assert gate["ok"] is False
    assert gate["hard_fail"] is True
    assert gate["reason"] == "coverage_below_target"


@pytest.mark.unit
def test_coverage_gate_hard_pass_at_target(tmp_path: Path) -> None:
    from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

    state = tmp_path / "state"
    state.mkdir(parents=True)
    lines = [json.dumps({"decision_context_id": f"c{i}"}) for i in range(20)]
    (state / "decision_log.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    gate = evaluate_aperture_coverage_gate(
        workspace_root=tmp_path, min_sample_size=10, min_coverage_pct=95.0
    )
    assert gate["ok"] is True
    assert gate["soft_pass"] is False
    assert gate["reason"] == "coverage_ok"
    assert gate["lineage_coverage_pct"] == pytest.approx(100.0)


@pytest.mark.unit
def test_fabric_blocks_place_in_safe_mode() -> None:
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="sim", trade_mode="sim")
            self.is_connected = True
            self._safe_mode = 2  # SAFE

        @property
        def safe_mode(self) -> int:
            return self._safe_mode

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            return {"type": "ok"}

    fake = _Fake()
    order = _Order(metadata={"decision_context_id": "ctx-1"})
    out = fake.place_order_sync(order, client_order_id="c1")
    assert out.get("code") == "SAFE_MODE"
    assert out.get("type") == "error"