"""Awakening PATH_EXIT K3: protocol, T_LOCK, flags, telem, eval. Shadow only."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_path_exit_k3 import (
    FORBIDDEN_WRITE_NAMES,
    INIT_SHA256,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    PATH_EARLY_A_NAME,
    T_LOCK,
    TRAIN_SEED,
    PathExitK3ProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    honesty_paragraph,
    overall_path_exit_k3_string,
    should_path_exit_k3,
)
from lumina_core.birth.awakening_path_exit_k3_flags import (
    TAG_HOLE_INTACT,
    TAG_HOLE_MOVED,
    TAG_S_HARM,
    TAG_S_MISSING,
    compute_path_exit_k3_flags,
    empty_baseline,
    flag_hole_moved,
    flag_s_harm,
    flag_s_missing_hook,
    flag_s_thin,
)
from lumina_core.birth.awakening_path_exit_k3_path import inspect_path_exit_k3_protocol
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row
from lumina_core.birth.sim_runner_entry_telem import close_open_telem, snapshot_path_at_k, start_open_telem


def _row(
    *,
    entry: str | None = "NEUTRAL",
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    trade_r: float = -1.04,
    pnl: float = -117.0,
    plant: bool = False,
    bars_held: int = 8,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": pnl,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
        "bars_held": bars_held,
    }
    if entry is not None:
        row["entry_regime"] = entry
    row.update(extra)
    return row


def test_inspect_path_exit_k3_protocol_complete() -> None:
    dump = inspect_path_exit_k3_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_t_lock_exact_float() -> None:
    assert T_LOCK == -0.04787176712367987
    src = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    assert "T_LOCK = -0.04787176712367987" in src


def test_should_path_exit_k3_gates() -> None:
    ok = dict(
        enabled=True,
        is_policy=True,
        entry_regime="NEUTRAL",
        bars_from_entry=3,
        unreal_r=T_LOCK,
    )
    assert should_path_exit_k3(**ok) is True
    assert should_path_exit_k3(**{**ok, "enabled": False}) is False
    assert should_path_exit_k3(**{**ok, "is_policy": False}) is False
    assert should_path_exit_k3(**{**ok, "bars_from_entry": 5}) is False
    assert should_path_exit_k3(**{**ok, "bars_from_entry": 2}) is False
    assert should_path_exit_k3(**{**ok, "unreal_r": None}) is False
    assert should_path_exit_k3(**{**ok, "unreal_r": T_LOCK + 0.01}) is False
    assert should_path_exit_k3(**{**ok, "entry_regime": None}) is False
    assert should_path_exit_k3(**{**ok, "entry_regime": "UNKNOWN"}) is False
    assert should_path_exit_k3(**{**ok, "unreal_r": T_LOCK - 0.01}) is True


def test_forbidden_write_path_early_jsonl(tmp_path: Path) -> None:
    assert PATH_EARLY_A_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathExitK3ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)


def test_default_hook_false_on_grind_run_signature() -> None:
    import inspect

    params = inspect.signature(run_evaluate_only).parameters
    assert params["path_exit_k3_shadow"].default is False


def test_flag_hole_moved_true_false() -> None:
    assert (
        flag_hole_moved(
            s_missing_hook=False,
            s_harm=False,
            n_h_shadow=60,
            n_h_base=78,
            mean_r_policy_shadow=-0.20,
            mean_r_policy_base=-0.30,
        )
        is True
    )
    assert (
        flag_hole_moved(
            s_missing_hook=False,
            s_harm=False,
            n_h_shadow=70,
            n_h_base=78,
            mean_r_policy_shadow=-0.20,
            mean_r_policy_base=-0.30,
        )
        is False
    )


def test_flag_s_harm() -> None:
    assert flag_s_harm(n_w_shadow=10, n_w_base=39, n_h_shadow=76, n_h_base=78) is True
    assert flag_s_harm(n_w_shadow=30, n_w_base=39, n_h_shadow=50, n_h_base=78) is False


def test_flag_s_missing_hook() -> None:
    assert flag_s_missing_hook(n_exit=0, n_still_open_at_3_baseline=117) is True
    assert flag_s_missing_hook(n_exit=1, n_still_open_at_3_baseline=117) is False
    assert flag_s_missing_hook(n_exit=0, n_still_open_at_3_baseline=10) is False


def test_flag_s_thin() -> None:
    assert flag_s_thin(n_policy=99) is True
    assert flag_s_thin(n_policy=100) is False


def test_compute_flags_hole_moved() -> None:
    base = {
        "n_H": 78,
        "mean_r_H": -1.04,
        "n_W": 39,
        "mean_r_W": 1.2,
        "n_policy": 150,
        "wr_policy": 0.307,
        "mean_r_policy": -0.40,
        "n_still_open_at_3": 117,
        "present": True,
    }
    holes = [_row() for _ in range(50)]
    winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(30)]
    exits = [
        _row(close_reason="force_exit", trade_r=-0.05, pnl=-5.0, path_exit_k3=True)
        for _ in range(40)
    ]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0) for _ in range(30)]
    flags = compute_path_exit_k3_flags(holes + winners + exits + extra, baseline=base)
    assert flags["HOLE_MOVED"] is True
    assert flags["tag"] == TAG_HOLE_MOVED
    assert flags["n_exit"] == 40
    assert flags["n_H"] == 50


def test_compute_flags_s_harm() -> None:
    base = {
        "n_H": 78,
        "mean_r_H": -1.04,
        "n_W": 39,
        "mean_r_W": 1.2,
        "n_policy": 150,
        "wr_policy": 0.307,
        "mean_r_policy": -0.40,
        "n_still_open_at_3": 117,
        "present": True,
    }
    holes = [_row() for _ in range(76)]
    winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(10)]
    exits = [_row(close_reason="force_exit", trade_r=-0.2, pnl=-10.0, path_exit_k3=True) for _ in range(5)]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0) for _ in range(59)]
    flags = compute_path_exit_k3_flags(holes + winners + exits + extra, baseline=base)
    assert flags["S_HARM"] is True
    assert flags["tag"] == TAG_S_HARM
    assert flags["HOLE_MOVED"] is False


def test_compute_flags_s_missing_hook() -> None:
    base = empty_baseline()
    base.update({"n_still_open_at_3": 117, "n_H": 78, "n_W": 39, "present": True, "mean_r_policy": -0.3})
    rows = [_row() for _ in range(80)] + [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(40)]
    flags = compute_path_exit_k3_flags(rows, baseline=base)
    assert flags["S_MISSING_HOOK"] is True
    assert flags["tag"] == TAG_S_MISSING


def test_telem_snapshot_then_hook_request() -> None:
    from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
    from lumina_core.birth.awakening_path_exit_k3_hook import after_open_telem_path_exit_k3

    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=10, entry_price=24000.0, side=1)
    stash["is_policy"] = True
    tick = {"close": 23900.0, "high": 24010.0, "low": 23890.0}
    snapshot_path_at_k(stash, tick, 3)
    assert "path_k3_unreal_usd" in stash
    assert stash["path_k3_unreal_usd"] < 0.0
    env = type("E", (), {"_idx": 13, "_entry_stop_pct": 0.0012, "_path_exit_k3_request": True})()
    token = PATH_EXIT_K3_SHADOW.set(True)
    try:
        after_open_telem_path_exit_k3(stash, env, [tick] * 20, {"close_reason": "force_exit"}, 3, 0)
    finally:
        PATH_EXIT_K3_SHADOW.reset(token)
    assert stash.get("path_exit_k3") is True
    assert "path_exit_k3_unreal_r" in stash
    assert stash["path_exit_k3_unreal_r"] <= T_LOCK


def test_ledger_copies_path_exit_k3_only_when_set() -> None:
    bare = close_ledger_row(
        {
            "pnl": -10.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "stop",
            "gap": False,
            "plant_entry": False,
            "entry_price": 20000.0,
            "risk_usd": 50.0,
            "trade_r": -0.2,
            "point_value": 5.0,
            "regime": "NEUTRAL",
        }
    )
    assert "path_exit_k3" not in bare
    assert "path_exit_k3_unreal_r" not in bare
    stamped = close_ledger_row(
        {
            **bare,
            "path_exit_k3": True,
            "path_exit_k3_unreal_r": T_LOCK,
            "pnl": -10.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "force_exit",
            "gap": False,
            "plant_entry": False,
            "entry_price": 20000.0,
            "risk_usd": 50.0,
            "trade_r": -0.2,
            "point_value": 5.0,
            "regime": "NEUTRAL",
        }
    )
    assert stamped["path_exit_k3"] is True
    assert stamped["path_exit_k3_unreal_r"] == T_LOCK
    telem = close_open_telem(
        {"path_exit_k3": True, "path_exit_k3_unreal_r": -0.1, "entry_regime": "NEUTRAL", "entry_bar_index": 1, "side": 1},
        4,
        "NEUTRAL",
        {"intended_risk_usd": 100.0},
    )
    assert telem["path_exit_k3"] is True
    assert telem["path_exit_k3_unreal_r"] == -0.1


def test_no_zero_impute_unreal() -> None:
    row = close_ledger_row(
        {
            "pnl": -10.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "stop",
            "gap": False,
            "plant_entry": False,
            "entry_price": 20000.0,
            "risk_usd": 50.0,
            "trade_r": -0.2,
            "point_value": 5.0,
            "regime": "NEUTRAL",
        }
    )
    assert "path_k3_unreal_r" not in row
    assert should_path_exit_k3(
        enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=None
    ) is False


def test_evaluate_only_policy_learn_raises() -> None:
    class _Inner:
        def predict(self, *args: Any, **kwargs: Any) -> Any:
            _ = args, kwargs
            return [0.0, 0.5, 0.002, 0.003], None

        def learn(self, *args: Any, **kwargs: Any) -> Any:
            return self

    wrapped = EvaluateOnlyPolicy(_Inner())
    with pytest.raises(RuntimeError, match="learn\\(\\) forbidden"):
        wrapped.learn(total_timesteps=1)
    with pytest.raises(PathExitK3ProtocolError, match="train seed"):
        assert_eval_seed(TRAIN_SEED)
    assert TRAIN is False
    assert overall_path_exit_k3_string(skip_replay=True) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_string(replay_ran=True, parent_loaded=True, optimizer_steps=0) == OVERALL_MEASURE
    assert honesty_paragraph(tag=TAG_HOLE_INTACT).count("T_LOCK=") == 1


def test_refuses_control_sha(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3 import CONTROL_ZIP_NAME

    control = tmp_path / CONTROL_ZIP_NAME
    control.write_bytes(b"nope")
    with pytest.raises(PathExitK3ProtocolError, match="refused"):
        assert_not_evaluated_policy(control)


def test_skip_replay_is_inconclusive(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3_run import run_path_exit_k3

    out = run_path_exit_k3(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert out["overall"] == OVERALL_INCONCLUSIVE
    assert out["skip_replay"] is True
    flags = json.loads((tmp_path / "artifacts" / "awakening_path_exit_k3_flags.json").read_text(encoding="utf-8"))
    assert flags["overall"] == OVERALL_INCONCLUSIVE
    assert INIT_SHA256.startswith("8cc435c6")
