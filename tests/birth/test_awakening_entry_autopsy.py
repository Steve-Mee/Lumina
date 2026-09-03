"""Awakening ENTRY hole autopsy: protocol, flags, serializer, eval wrap, contrast."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_entry_autopsy import (
    ENTRY_A_NAME,
    FORBIDDEN_WRITE_NAMES,
    INIT_SHA256,
    TRAIN_SEED,
    EntryAutopsyProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    compute_entry_flags,
    flag_h_entry_flip,
    flag_h_entry_neutral,
    flag_h_first_touch,
    flag_h_missing_entry,
    isolated_workspace,
    licensed_future_family,
    read_existing_hole_contrast,
)
from lumina_core.birth.awakening_entry_autopsy_path import inspect_entry_autopsy_protocol
from lumina_core.birth.awakening_entry_autopsy_run import run_entry_eval_leg
from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row


def _hole(
    *,
    entry: str | None,
    bars_held: int | None = 10,
    mae_r: float | None = -1.0,
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    plant: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": -117.0,
        "trade_r": -1.04,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
    }
    if entry is not None:
        row["entry_regime"] = entry
    if bars_held is not None:
        row["bars_held"] = bars_held
    if mae_r is not None:
        row["mae_r"] = mae_r
    return row


def test_a_protocol_isolation(tmp_path: Path) -> None:
    dump = inspect_entry_autopsy_protocol()
    assert dump["missing_sites"] == []
    assert dump["gate0_complete"] is True
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"
    with pytest.raises(EntryAutopsyProtocolError, match="train seed 20260901"):
        assert_eval_seed(TRAIN_SEED)
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "awakening_select_pi_star.zip")
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "awakening_hole_tax_pi_star.zip")
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "grind_A_close_ledger.jsonl")
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "select_A_close_ledger.jsonl")
    with pytest.raises(EntryAutopsyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "hole_tax_A_close_ledger.jsonl")
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04decoy")
    with pytest.raises(EntryAutopsyProtocolError, match="gitignored ppo"):
        assert_isolated_write(ppo)
    control = tmp_path / "artifacts" / "awakening_select_pi_star.zip"
    control.parent.mkdir(parents=True)
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(EntryAutopsyProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(control)
    hole_tax = tmp_path / "artifacts" / "awakening_hole_tax_pi_star.zip"
    hole_tax.write_bytes(b"PK\x03\x04hole-tax")
    with pytest.raises(EntryAutopsyProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(hole_tax)
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_entry_autopsy/workspace")
    assert ENTRY_A_NAME not in FORBIDDEN_WRITE_NAMES
    assert TRAIN is False
    src_run = Path("lumina_core/birth/awakening_entry_autopsy_run.py").read_text(encoding="utf-8")
    assert "learn_fn" not in src_run
    assert "model.learn(" not in src_run
    assert "model.learn" not in src_run


def test_b_flags_synthetic_rows() -> None:
    neu = [_hole(entry="NEUTRAL") for _ in range(28)] + [_hole(entry="TREND_UP") for _ in range(12)]
    flags = compute_entry_flags(neu)
    assert flags["n_H"] == 40
    assert flags["H_ENTRY_NEUTRAL"] is True
    assert flags["H_ENTRY_FLIP"] is False
    assert flag_h_entry_neutral(h_missing=False, frac_neu=0.70) is True

    flip = [_hole(entry="TREND_UP") for _ in range(11)] + [_hole(entry="TREND_DOWN") for _ in range(11)]
    flip += [_hole(entry="NEUTRAL") for _ in range(18)]
    flags_f = compute_entry_flags(flip)
    assert flags_f["n_H"] == 40
    assert flags_f["H_ENTRY_FLIP"] is True
    assert flags_f["H_ENTRY_NEUTRAL"] is False

    missing = [_hole(entry=None) for _ in range(10)] + [_hole(entry="NEUTRAL") for _ in range(30)]
    flags_m = compute_entry_flags(missing)
    assert flags_m["H_MISSING_ENTRY"] is True
    assert flag_h_missing_entry(n_h=40, missing_entry=0.25) is True

    small = [_hole(entry="NEUTRAL") for _ in range(30)]
    flags_s = compute_entry_flags(small)
    assert flags_s["H_MISSING_ENTRY"] is True
    assert flag_h_missing_entry(n_h=30, missing_entry=0.0) is True

    ft = [_hole(entry="NEUTRAL", bars_held=2) for _ in range(25)] + [
        _hole(entry="NEUTRAL", bars_held=10) for _ in range(5)
    ]
    ft += [_hole(entry="TREND_UP", bars_held=10) for _ in range(10)]
    flags_ft = compute_entry_flags(ft)
    assert flags_ft["H_ENTRY_NEUTRAL"] is True
    assert flags_ft["H_FIRST_TOUCH"] is True
    assert flag_h_first_touch(h_missing=False, h_neutral=True, frac_ft=0.50) is True

    mixed = licensed_future_family(h_missing=False, h_neutral=True, h_flip=True)
    assert mixed == "H_MIXED"
    assert licensed_future_family(h_missing=False, h_neutral=True, h_flip=False) == "OPEN_DECISION"
    assert licensed_future_family(h_missing=False, h_neutral=False, h_flip=True) == "REGIME_FLIP_EXIT"
    assert flag_h_entry_flip(h_missing=False, frac_tr=0.50) is True


def test_c_serializer_additive() -> None:
    old = close_ledger_row(
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
            "reward_on_close": -0.2,
        }
    )
    for key in (
        "pnl",
        "qty",
        "cap_usd",
        "close_reason",
        "gap",
        "plant",
        "force_open",
        "entry_price",
        "risk_usd",
        "intended_risk_usd",
        "trade_r",
        "point_value",
        "regime",
        "reward_on_close",
        "cap_hit",
    ):
        assert key in old
    assert "mae_r" not in old
    assert "mfe_r" not in old
    assert "entry_regime" not in old
    assert old.get("mae_r") != 0.0

    filled = close_ledger_row(
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
            "entry_regime": "TREND_UP",
            "close_regime": "NEUTRAL",
            "entry_bar_index": 10,
            "close_bar_index": 14,
            "bars_held": 4,
            "mae_r": -0.8,
            "mfe_r": 0.2,
            "regime_flip": True,
            "skill_grade": "policy",
            "source": "awakening_entry_autopsy",
        }
    )
    assert filled["entry_regime"] == "TREND_UP"
    assert filled["close_regime"] == "NEUTRAL"
    assert filled["mae_r"] == pytest.approx(-0.8)
    assert filled["bars_held"] == 4
    assert filled["source"] == "awakening_entry_autopsy"


def test_d_evaluate_only_policy_and_runner_no_learn(tmp_path: Path) -> None:
    class _Inner:
        learn_calls = 0

        def predict(self, *args: Any, **kwargs: Any) -> Any:
            _ = args, kwargs
            return [0.0, 0.5, 0.002, 0.003], None

        def learn(self, *args: Any, **kwargs: Any) -> Any:
            self.learn_calls += 1
            return self

    wrapped = EvaluateOnlyPolicy(_Inner())
    with pytest.raises(RuntimeError, match="learn\\(\\) forbidden"):
        wrapped.learn(total_timesteps=1)
    src = Path("lumina_core/birth/awakening_entry_autopsy_run.py").read_text(encoding="utf-8")
    assert "learn_fn" not in src
    assert "model.learn" not in src
    child = tmp_path / "parent.zip"
    child.write_bytes(b"PK\x03\x04parent")

    def _stub_rollout(**kwargs: Any) -> SimpleNamespace:
        _ = kwargs
        return SimpleNamespace(
            trajectories=[],
            rollout_steps=0,
            plant_trades=0,
            policy_trades=0,
            optimizer_steps=0,
        )

    with pytest.raises(EntryAutopsyProtocolError, match="train seed|eval seed"):
        run_entry_eval_leg(
            seed=20260901,
            holdout=[{"close": 1.0}],
            workspace_root=tmp_path,
            reports=tmp_path,
            policy_path=child,
            rollout_fn=_stub_rollout,
        )


def test_e_contrast_reader_absent(tmp_path: Path) -> None:
    missing = tmp_path / "grind_A_close_ledger.jsonl"
    out = read_existing_hole_contrast(missing)
    assert out["absent"] is True
    assert "n" not in out
    assert out.get("mean_r") is None or "mean_r" not in out


def test_f_isolation_regex_still_green() -> None:
    from tests.engine.test_economic_pnl_service import (
        test_lumina_core_non_rl_modules_exclude_training_reward_token,
    )

    test_lumina_core_non_rl_modules_exclude_training_reward_token()
    sidecar = Path("reports/birth_cloud_run/artifacts/birth_exit_pi_star.json")
    if sidecar.is_file():
        import json

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload.get("sha256") == INIT_SHA256
