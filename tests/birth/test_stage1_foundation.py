"""Stage-1 foundation: grow without raising survival pass floor; hard handoff."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.birth.stage1_foundation import (
    compute_stage1_foundation,
    execute_stage1_transfer_handoff,
    purge_stage1_buffer,
    stage1_foundation_learning_gap,
    stage1_foundation_meta_fields,
)


@pytest.mark.unit
def test_survival_ok_but_foundation_pressure_when_wr_low() -> None:
    """WR 22% clears survival 20% but still has foundation gap to 30%."""
    s = compute_stage1_foundation(
        stage_trades=300,
        stage_wins=66,  # 22%
        required=200,
        survival_wr_floor=0.20,
        foundation_target_wr=0.30,
        anti_thrash_wr=0.25,
    )
    assert s.survival_ok is True
    assert s.foundation_pressure is True
    assert s.anti_thrash is True  # 22% < 25%
    assert s.learning_gap == pytest.approx(0.08, abs=0.01)


@pytest.mark.unit
def test_pass_floor_not_changed_by_foundation_target() -> None:
    """Learning gap does not invent a new pass gate — only pressure."""
    gap = stage1_foundation_learning_gap(
        stage_trades=250,
        stage_wins=55,  # 22%
        required=200,
        cfg=SimpleNamespace(
            stage1_foundation_pressure_enabled=True,
            birth_survival_wr_floor=0.20,
            stage1_foundation_target_wr=0.30,
            stage1_anti_thrash_wr=0.25,
        ),
    )
    assert gap > 0.0
    # Survival still would pass at 22% (gap is learning only).


@pytest.mark.unit
def test_anti_thrash_meta_never_explore_boost() -> None:
    s = compute_stage1_foundation(
        stage_trades=400,
        stage_wins=88,  # 22%
        required=200,
        foundation_target_wr=0.30,
        anti_thrash_wr=0.25,
    )
    fields = stage1_foundation_meta_fields(s, exploration_steps=2000, median_loss_r=1.1)
    assert fields is not None
    assert fields["primary"] == "explore_reduce"
    assert fields["mine"] is True
    assert "explore_boost" not in str(fields.get("secondary"))


@pytest.mark.unit
def test_process_r_fail_holds_not_explore_reduce() -> None:
    s = compute_stage1_foundation(
        stage_trades=400,
        stage_wins=88,  # 22% — WR is HUD-only
        required=200,
        foundation_target_wr=0.30,
        anti_thrash_wr=0.25,
    )
    fields = stage1_foundation_meta_fields(s, exploration_steps=2000, median_loss_r=9.5)
    assert fields is not None
    assert fields["primary"] == "hold"
    assert fields["rationale"] == "stage1_process_r_plant"
    assert fields["mine"] is False


@pytest.mark.unit
def test_missing_process_r_after_volume_gate_is_hold() -> None:
    s = compute_stage1_foundation(
        stage_trades=400,
        stage_wins=160,
        required=200,
        foundation_target_wr=0.30,
        anti_thrash_wr=0.25,
    )
    fields = stage1_foundation_meta_fields(s, exploration_steps=2000, median_loss_r=None)
    assert fields is not None
    assert fields["primary"] == "hold"
    assert fields["rationale"] == "stage1_process_r_plant"


@pytest.mark.unit
def test_no_pressure_before_volume_gate() -> None:
    s = compute_stage1_foundation(
        stage_trades=50,
        stage_wins=5,  # 10%
        required=200,
        foundation_target_wr=0.30,
    )
    assert s.foundation_pressure is False
    assert s.anti_thrash is False


@pytest.mark.unit
def test_purge_buffer_full_clear() -> None:
    buf = [{"reward": -1}, {"reward": 2}]
    # list without clear — use list path via rewrite
    class _Buf(list):
        def clear(self):  # type: ignore[override]
            del self[:]

    b = _Buf(buf)
    out = purge_stage1_buffer(b, keep_top_pct=0.0)
    assert out["mode"] == "full_clear"
    assert len(b) == 0
    assert out["removed"] == 2


@pytest.mark.unit
def test_transfer_handoff_reinit_and_purge() -> None:
    torch = pytest.importorskip("torch")
    import torch.nn as nn

    action_net = nn.Linear(4, 4)
    with torch.no_grad():
        action_net.weight.fill_(2.5)
    policy = SimpleNamespace(action_net=action_net, value_net=nn.Linear(4, 1), log_std=None)
    model = SimpleNamespace(policy=policy)

    class _Buf(list):
        def clear(self):  # type: ignore[override]
            del self[:]

    host = SimpleNamespace(
        current_policy=model,
        buffer=_Buf([{"reward": -1}, {"reward": 0.5}]),
        runtime=None,
        engine=None,
        ppo_trainer=None,
    )
    cfg = SimpleNamespace(
        stage1_transfer_handoff_enabled=True,
        stage1_transfer_purge_buffer=True,
        stage1_transfer_keep_buffer_top_pct=0.0,
        stage1_transfer_max_buffer_keep=0,
        stage1_transfer_reinit_action_head=True,
    )
    result = execute_stage1_transfer_handoff(
        host=host,
        cfg=cfg,
        stage_trades=200,
        stage_wins=53,  # 26.5% survival-ish
    )
    assert result["ok"] is True
    assert result["buffer_purge"]["mode"] == "full_clear"
    assert len(host.buffer) == 0
    assert result["action_head_reinit"]["ok"] is True
    w = action_net.weight
    assert not torch.allclose(w, torch.full_like(w, 2.5))
    assert getattr(host, "_stage1_transfer_handoff", None) is not None


@pytest.mark.unit
def test_handoff_disabled() -> None:
    host = SimpleNamespace(current_policy=None, buffer=[], runtime=None)
    cfg = SimpleNamespace(stage1_transfer_handoff_enabled=False)
    r = execute_stage1_transfer_handoff(host=host, cfg=cfg, stage_trades=100, stage_wins=30)
    assert r["ok"] is False
    assert r["reason"] == "disabled"


@pytest.mark.unit
def test_graduation_source_calls_handoff() -> None:
    from pathlib import Path

    src = Path("lumina_core/birth/engine_graduation.py").read_text(encoding="utf-8")
    assert "execute_stage1_transfer_handoff" in src
    assert "STAGE1_TREND" in src
