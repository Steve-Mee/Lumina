"""Awakening hole-tax: floors, split refuse, pins, tax fixture, init refuse, flags."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_grind import (
    BIRTH_MEAN_USD,
    BIRTH_N,
    REGRESS_MEAN_USD,
    TRAIN,
)
from lumina_core.birth.awakening_hole_tax import (
    AWAKENING_HOLE_TAX_PPO_TIMESTEPS,
    AWAKENING_HOLE_TAX_R,
    CONTROL_SHA256,
    EVAL_B_SEED,
    INIT_SHA256,
    TRAIN_SEED,
    HoleTaxProtocolError,
    apply_hole_tax,
    assert_budget,
    assert_init_sha,
    assert_isolated_write,
    assert_not_control_init,
    assert_not_holdout_b_path,
    assert_train_seed,
    hole_moved,
    hole_substitution,
    overall_hole_tax_string,
    resolve_hole_tax_init_path,
    select_overfit,
)
from lumina_core.birth.awakening_hole_tax_run import load_hole_tax_train_tape, run_hole_tax_train
from lumina_core.birth.birth_exit_policy_export import (
    is_gitignored_ppo_zip,
    resolve_frozen_policy_path,
)
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
from lumina_core.rl.gym_stop_fill import birth_force_qty_one


def test_a_floors_and_settlement_still_pinned() -> None:
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert S5_DD_EQUITY_USD == pytest.approx(50_000.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True
    assert BIRTH_N == 172
    assert BIRTH_MEAN_USD == pytest.approx(-20.7)
    assert REGRESS_MEAN_USD == pytest.approx(-62.0)
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics
    tree_files = [
        "lumina_core/birth/awakening_hole_tax.py",
        "lumina_core/birth/awakening_hole_tax_run.py",
        "lumina_core/birth/awakening_select_env.py",
        "lumina_core/birth/awakening_grind.py",
    ]
    for rel in tree_files:
        src = Path(rel).read_text(encoding="utf-8")
        for token in ("S5_IDLE_REGIMES", "MAX_PLANT", "MAX_TIME_STOP", "if synthetic"):
            assert token not in src


def test_b_train_split_refuse(tmp_path: Path) -> None:
    with pytest.raises(HoleTaxProtocolError, match="holdout seed 20260903"):
        assert_train_seed(EVAL_B_SEED)
    with pytest.raises(HoleTaxProtocolError, match="holdout seed 20260902"):
        assert_train_seed(20260902)
    with pytest.raises(HoleTaxProtocolError, match="holdout B path"):
        assert_not_holdout_b_path(tmp_path / "holdout_b" / "tape.jsonl")
    with pytest.raises(HoleTaxProtocolError, match="holdout B path"):
        assert_not_holdout_b_path("/tmp/workspace_grind_b")
    with pytest.raises(HoleTaxProtocolError, match="20260903"):
        load_hole_tax_train_tape(seed=20260903, workspace=tmp_path)
    with pytest.raises(HoleTaxProtocolError, match="20260902"):
        load_hole_tax_train_tape(seed=20260902, workspace=tmp_path)
    with pytest.raises(HoleTaxProtocolError, match="holdout B"):
        load_hole_tax_train_tape(
            seed=TRAIN_SEED, workspace=tmp_path, holdout_b_path=tmp_path / "holdout_b"
        )
    with pytest.raises(HoleTaxProtocolError, match="holdout seed"):
        run_hole_tax_train(seed=20260902, workspace_root=tmp_path, reports=tmp_path)
    with pytest.raises(HoleTaxProtocolError, match="holdout seed"):
        run_hole_tax_train(seed=20260903, workspace_root=tmp_path, reports=tmp_path)


def test_c_pins() -> None:
    assert AWAKENING_HOLE_TAX_R == pytest.approx(1.0)
    assert AWAKENING_HOLE_TAX_PPO_TIMESTEPS == 10_000
    assert isinstance(AWAKENING_HOLE_TAX_PPO_TIMESTEPS, int)
    assert assert_budget(AWAKENING_HOLE_TAX_PPO_TIMESTEPS) == 10_000
    with pytest.raises(HoleTaxProtocolError, match="outside pin window"):
        assert_budget(100_000)


def test_d_tax_fixture_and_eval_untaxed() -> None:
    assert apply_hole_tax(-1.038, "stop", "NEUTRAL") == pytest.approx(-2.038)
    assert apply_hole_tax(-1.038, "stop", "TREND_DOWN") == pytest.approx(-1.038)
    assert apply_hole_tax(+1.212, "target", "NEUTRAL") == pytest.approx(+1.212)
    assert apply_hole_tax(+1.342, "time_stop", "NEUTRAL") == pytest.approx(+1.342)
    row = {
        "trade_r": -1.038,
        "pnl": -117.0,
        "close_reason": "stop",
        "regime": "NEUTRAL",
    }
    taxed = apply_hole_tax(float(row["trade_r"]), str(row["close_reason"]), str(row["regime"]))
    assert taxed == pytest.approx(-2.038)
    assert float(row["trade_r"]) == pytest.approx(-1.038)
    assert float(row["pnl"]) == pytest.approx(-117.0)


def test_e_init_refuse(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04post_polish_decoy")
    assert is_gitignored_ppo_zip(ppo) is True
    assert resolve_frozen_policy_path(tmp_path) is None
    with pytest.raises(HoleTaxProtocolError, match="refused gitignored ppo"):
        assert_init_sha(ppo)
    dest = resolve_hole_tax_init_path(tmp_path)
    assert dest.name == "birth_exit_pi_star.zip"
    assert "lumina_agents/ppo" not in dest.as_posix()
    assert dest.name != "awakening_select_pi_star.zip"
    control = tmp_path / "artifacts" / "awakening_select_pi_star.zip"
    control.parent.mkdir(parents=True)
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(HoleTaxProtocolError, match="control zip"):
        assert_not_control_init(control)
    with pytest.raises(HoleTaxProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(HoleTaxProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "select_A_close_ledger.jsonl")
    with pytest.raises(HoleTaxProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "awakening_select_pi_star.zip")
    with pytest.raises(HoleTaxProtocolError, match="gitignored ppo"):
        assert_isolated_write(ppo)


def test_f_flags() -> None:
    assert hole_substitution(
        parent_hole_n=83, child_hole_n=60, parent_plant_fo=68, child_plant_fo=90
    ) is True
    assert hole_substitution(
        parent_hole_n=83, child_hole_n=79, parent_plant_fo=68, child_plant_fo=75
    ) is False
    assert select_overfit(wr_policy_a=0.40, wr_policy_b=0.29) is True
    assert select_overfit(wr_policy_a=0.333, wr_policy_b=0.387) is False
    assert hole_moved(hole_n_a=79, mean_r_policy_a=-0.274) is False
    assert hole_moved(hole_n_a=50, mean_r_policy_a=-0.274) is True
    tagged = overall_hole_tax_string(
        "GRIND_REGRESS", "INCONCLUSIVE", overfit=False, substitution=False, moved=False
    )
    assert "GRIND_REGRESS_AWAKENING_OPEN" in tagged
    assert "HOLE_TAX_SHOT" in tagged
    assert "SELECT_OVERFIT=false" in tagged
    assert "HOLE_SUBSTITUTION=false" in tagged
    assert "HOLE_MOVED=false" in tagged
    assert TRAIN is False


def test_init_sha_constant_matches_birth_exit_sidecar() -> None:
    sidecar = Path("reports/birth_cloud_run/artifacts/birth_exit_pi_star.json")
    if sidecar.is_file():
        import json

        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        assert payload.get("sha256") == INIT_SHA256
    zip_path = Path("reports/birth_cloud_run/artifacts/birth_exit_pi_star.zip")
    if zip_path.is_file():
        assert assert_init_sha(zip_path) == INIT_SHA256
    control_meta = Path("reports/birth_cloud_run/artifacts/awakening_select_pi_star.json")
    if control_meta.is_file():
        import json

        payload = json.loads(control_meta.read_text(encoding="utf-8"))
        assert payload.get("sha256") == CONTROL_SHA256
    control_zip = Path("reports/birth_cloud_run/artifacts/awakening_select_pi_star.zip")
    if control_zip.is_file():
        with pytest.raises(HoleTaxProtocolError, match="control"):
            assert_not_control_init(control_zip)
