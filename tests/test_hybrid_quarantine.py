"""Hybrid quarantine gates: defaults preserve legacy; strict fails closed."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_inventory_defaults_preserve_legacy() -> None:
    from lumina_core.hybrid_quarantine import inventory

    with patch("lumina_core.hybrid_quarantine._cfg", return_value={}):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("LUMINA_HYBRID_STRICT", None)
            inv = inventory()
    assert inv["multi_day_sim"] is False
    assert inv["shadow_trace_verdict"] is False
    assert inv["arch_patch_apply"] is False
    assert inv["kill_switch_auth"] is False
    assert inv["plateau_terminal_passthrough"] is True
    assert inv["vllm_lifecycle"] is False


@pytest.mark.unit
def test_sim_strict_profile_via_config() -> None:
    from lumina_core import hybrid_quarantine as hq

    cfg = {"mode": "sim", "hybrid_quarantine": {"apply_strict_in_sim": True}}
    with patch.object(hq, "_cfg", return_value=cfg):
        with patch.dict("os.environ", {"LUMINA_HYBRID_STRICT": ""}, clear=False):
            assert hq.sim_strict_profile_active() is True
            assert hq.require_true_backtest() is True
            assert hq.require_trace_verdict() is True
            assert hq.require_real_patch_apply() is True
            assert hq.require_kill_switch_reset_authorization() is True
            assert hq.handler_terminal_passthrough() is False
            assert hq.manage_vllm_lifecycle() is True


@pytest.mark.unit
def test_sim_strict_profile_via_env() -> None:
    from lumina_core import hybrid_quarantine as hq

    cfg = {"mode": "paper", "hybrid_quarantine": {"apply_strict_in_sim": False}}
    with patch.object(hq, "_cfg", return_value=cfg):
        with patch.dict("os.environ", {"LUMINA_HYBRID_STRICT": "1"}, clear=False):
            assert hq.sim_strict_profile_active() is True
            assert hq.require_true_backtest() is True


@pytest.mark.unit
def test_sim_strict_profile_ignored_in_real() -> None:
    from lumina_core import hybrid_quarantine as hq

    cfg = {"mode": "real", "hybrid_quarantine": {"apply_strict_in_sim": True}}
    with patch.object(hq, "_cfg", return_value=cfg):
        with patch.dict("os.environ", {"LUMINA_HYBRID_STRICT": "1"}, clear=False):
            assert hq.sim_strict_profile_active() is False
            assert hq.require_true_backtest() is False
            assert hq.handler_terminal_passthrough() is True


@pytest.mark.unit
def test_kill_switch_reset_requires_auth_when_strict() -> None:
    from lumina_core.risk.risk_gates import RiskGatesMixin

    class _Host(RiskGatesMixin):
        def __init__(self) -> None:
            self.state = MagicMock()
            self.state.kill_switch_engaged = True
            self.state.kill_switch_reason = "test"
            self.state.kill_switch_time = None

        def _save_state(self) -> None:
            return None

    host = _Host()
    with patch(
        "lumina_core.hybrid_quarantine.require_kill_switch_reset_authorization",
        return_value=True,
    ):
        assert host.reset_kill_switch("") is False
        assert host.state.kill_switch_engaged is True
        assert host.reset_kill_switch("ok") is True
        assert host.state.kill_switch_engaged is False


@pytest.mark.unit
def test_arch_sandbox_strict_refuses_optimistic_delta() -> None:
    from lumina_core.architecture_meta.sandbox import ArchitectureMutationSandbox

    sand = ArchitectureMutationSandbox(repo_root=Path("."))
    with patch("lumina_core.hybrid_quarantine.require_real_patch_apply", return_value=True):
        ok, score = sand._simulate_apply_and_measure(Path("."), "x.py", "extract helper", 5.0)
    assert ok is False
    assert score == 5.0


@pytest.mark.unit
def test_arch_sandbox_default_keeps_optimistic_delta() -> None:
    from lumina_core.architecture_meta.sandbox import ArchitectureMutationSandbox

    sand = ArchitectureMutationSandbox(repo_root=Path("."))
    with patch("lumina_core.hybrid_quarantine.require_real_patch_apply", return_value=False):
        ok, score = sand._simulate_apply_and_measure(Path("."), "x.py", "extract helper", 5.0)
    assert ok is True
    assert score == pytest.approx(5.22)


@pytest.mark.unit
def test_multi_day_strict_returns_neg_inf_on_rng_path() -> None:
    from lumina_core.evolution.dna_registry import PolicyDNA
    from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner

    runner = MultiDaySimRunner()
    variant = PolicyDNA(
        prompt_id="test",
        version="1",
        hash="abc123",
        content="{}",
        fitness_score=0.0,
        generation=0,
        parent_ids=(),
    )
    with patch("lumina_core.hybrid_quarantine.require_true_backtest", return_value=True):
        result = runner._evaluate_single_variant(
            variant,
            days=3,
            report={"net_pnl": 10.0, "sharpe": 1.0, "max_drawdown": 1.0, "account_equity": 50000.0},
            shadow_mode=False,
            real_market_data=False,
            true_backtest_mode=False,
        )
    assert result.fitness == float("-inf")
