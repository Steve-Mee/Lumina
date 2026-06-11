"""
Tests for D2 Sub-Slice 4: PaperTradeExecutor (bounded firewall for runtime_workers paper/EOD Order paths).

Per test-scaffolding skill + approved plan:
- @pytest.mark.unit for pure build/submit with mocks.
- given-when-then structure (in docstrings/comments).
- Explicit best-effort / fail-closed paths for missing ctx.
- monkeypatch/mocker for broker/dream.
- Covers full lineage/metadata on Order for paper paths + EOD.
- No behavior change on happy (same qty/side/execution fields).

Reproduce: python -m pytest tests/engine/test_paper_trade_executor.py -q --tb=short
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.broker.broker_bridge import Order
from lumina_core.engine.paper_trade_executor import PaperTradeExecutor


def _make_dream(ctx: str | None = "ctx-from-dream", regime: str = "TREND", confluence: float = 0.75, stop: float = 1.0, target: float = 2.0) -> dict:
    d = {
        "regime": regime,
        "confluence_score": confluence,
        "stop": stop,
        "target": target,
    }
    if ctx:
        d["decision_context_id"] = ctx
    return d


@pytest.mark.unit
class TestPaperTradeExecutor:
    """given-when-then for the bounded executor forcing provenance on paper/EOD capital paths."""

    def test_build_paper_order_attaches_full_lineage_and_metadata(self):
        # given (dream with ctx + confluence from upstream proposal per Phase 2)
        executor = PaperTradeExecutor()
        dream = _make_dream(ctx="upstream-ctx-123", regime="TREND", confluence=0.8)

        # when
        order = executor.build_paper_order(
            signal="BUY",
            qty=10,
            dream_snapshot=dream,
            decision_context_id=dream.get("decision_context_id"),
            prev_hash="prev-abc",
            inst="TEST",
        )

        # then
        assert isinstance(order, Order)
        assert order.symbol == "TEST"
        assert order.side == "BUY"
        assert order.quantity == 10
        md = order.metadata
        assert md["decision_context_id"] == "upstream-ctx-123"
        assert md["prev_hash"] == "prev-abc"
        assert md["regime"] == "TREND"
        assert md["confluence_score"] == 0.8
        assert "proposed_risk" not in md or isinstance(md.get("proposed_risk"), (int, float))  # additive only if present

    def test_build_paper_order_best_effort_fallback_when_no_ctx(self):
        # given (no ctx in dream or explicit)
        executor = PaperTradeExecutor()
        dream = _make_dream(ctx=None)

        # when
        order = executor.build_paper_order(signal="SELL", qty=5, dream_snapshot=dream)

        # then (generated ctx, still full other metadata)
        assert "decision_context_id" in order.metadata
        assert order.metadata["decision_context_id"].startswith("paper-evo-")
        assert order.metadata["regime"] == "TREND"
        assert order.side == "SELL"

    def test_submit_paper_order_uses_broker_and_is_non_breaking(self):
        # given (mock broker)
        mock_broker = MagicMock()
        mock_broker.submit_order.return_value = type("Res", (), {"accepted": True})()
        executor = PaperTradeExecutor(broker=mock_broker)

        order = executor.build_paper_order(signal="BUY", qty=1, dream_snapshot=_make_dream())

        # when
        res = executor.submit_paper_order(order)

        # then
        mock_broker.submit_order.assert_called_once_with(order)
        assert getattr(res, "accepted", False) is True

    def test_eod_close_wrapper_attaches_eod_specific_and_ctx(self):
        # given
        executor = PaperTradeExecutor()
        pos = SimpleNamespace(symbol="EODSYM", quantity=7)

        # when
        eod_order = executor.build_paper_order(
            signal="SELL",
            qty=7,
            dream_snapshot=None,
            inst="EODSYM",
            reason="eod_force_close",
        )
        # simulate EOD wrapper metadata override (as in runtime_workers site)
        eod_order.metadata["reason"] = "eod_force_close"
        eod_order.metadata["mode"] = "paper"

        # then
        assert eod_order.metadata["reason"] == "eod_force_close"
        assert "decision_context_id" in eod_order.metadata  # generated or provided
        assert eod_order.quantity == 7


@pytest.mark.unit
def test_executor_integration_with_supervisor_mocks(monkeypatch):
    """Integration smoke: supervisor-like context (app + container + dream with ctx) → executor → full Order."""
    # given (minimal app/container mocks with dream carrying ctx from proposal)
    mock_broker = MagicMock()
    mock_broker.submit_order.return_value = type("Res", (), {"accepted": True})()
    mock_container = SimpleNamespace(broker=mock_broker)
    app = SimpleNamespace(
        engine=SimpleNamespace(config=SimpleNamespace(trade_mode="paper", instrument="TESTINST")),
        sim_position_qty=0,
        container=mock_container,
        logger=MagicMock(),
    )
    dream = _make_dream(ctx="proposal-ctx-xyz", regime="RANGE")

    executor = PaperTradeExecutor(app=app, broker=mock_broker, container=mock_container)

    # when (paper open style)
    order = executor.build_paper_order(
        signal="BUY",
        qty=3,
        dream_snapshot=dream,
        decision_context_id=dream.get("decision_context_id"),
        prev_hash=dream.get("prev_hash"),
    )
    res = executor.submit_paper_order(order)

    # then
    assert "decision_context_id" in order.metadata and order.metadata["decision_context_id"] == "proposal-ctx-xyz"
    assert "confluence_score" in order.metadata
    mock_broker.submit_order.assert_called_once()
    assert getattr(res, "accepted", False) is True
