"""Awakening PATH_UNREAL_K3: protocol, single-candidate flags, runner. Measure-only."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_path_early_flags import PATH_CANDIDATE_RAW_KEY
from lumina_core.birth.awakening_path_early_path import compute_k_medians, pred_unreal_red, universe_k
from lumina_core.birth.awakening_path_unreal_k3 import (
    FORBIDDEN_WRITE_NAMES,
    INIT_ZIP_NAME,
    LOCKED_COV_H_A,
    LOCKED_LIFT_A,
    LOCKED_PATH_EARLY_A,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    PATH_EARLY_A_NAME,
    PATH_EARLY_B_NAME,
    TRAIN_SEED,
    PathUnrealK3ProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    honesty_paragraph,
    overall_path_unreal_k3_string,
)
from lumina_core.birth.awakening_path_unreal_k3_flags import (
    CANDIDATE_NAMES,
    FAMILY_H_NONE,
    FAMILY_PATH_EXIT_P_K3_UNREAL_RED,
    K_LOCKED,
    P_K3_UNREAL_RED,
    RAW_KEY,
    TAG_S_MULTI,
    compute_path_unreal_k3_flags,
    flip_row,
    license_from_ab_k3,
)
from lumina_core.birth.awakening_path_unreal_k3_path import inspect_path_unreal_k3_protocol
from lumina_core.birth.awakening_path_unreal_k3_tables import table_t5
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row


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


def _split_k3_unreal(
    *,
    n_h_red: int,
    n_h_ok: int,
    n_w_red: int,
    n_w_ok: int,
    n_other_red: int = 0,
    n_other_ok: int = 0,
    also_mae: bool = False,
    also_k5: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _add(n: int, *, red: bool, winner: bool, other: bool) -> None:
        unreal = -2.0 if red else 0.0
        extra: dict[str, Any] = {"path_k3_unreal_r": unreal, "path_k3_mfe_r": 0.5}
        if also_mae:
            extra["path_k3_mae_r"] = unreal
        if also_k5:
            extra["path_k5_unreal_r"] = unreal
            extra["path_k5_mae_r"] = unreal
        if other:
            rows.extend(
                _row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, **extra) for _ in range(n)
            )
        elif winner:
            rows.extend(_row(close_reason="target", trade_r=1.21, pnl=60.0, **extra) for _ in range(n))
        else:
            rows.extend(_row(**extra) for _ in range(n))

    _add(n_h_red, red=True, winner=False, other=False)
    _add(n_h_ok, red=False, winner=False, other=False)
    _add(n_w_red, red=True, winner=True, other=False)
    _add(n_w_ok, red=False, winner=True, other=False)
    _add(n_other_red, red=True, winner=False, other=True)
    _add(n_other_ok, red=False, winner=False, other=True)
    return rows


def test_inspect_path_unreal_k3_protocol_complete() -> None:
    dump = inspect_path_unreal_k3_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []
    assert K_LOCKED == 3
    assert CANDIDATE_NAMES == (P_K3_UNREAL_RED,)


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_candidate_names_only_k3_unreal() -> None:
    assert CANDIDATE_NAMES == (P_K3_UNREAL_RED,)
    assert len(CANDIDATE_NAMES) == 1
    assert RAW_KEY == PATH_CANDIDATE_RAW_KEY[P_K3_UNREAL_RED] == "path_k3_unreal_r"
    assert "P_K5_UNREAL_RED" not in CANDIDATE_NAMES
    assert "P_K3_MAE_DEEP" not in CANDIDATE_NAMES
    assert "P_UNREAL_RED" not in CANDIDATE_NAMES


def test_forbidden_write_path_early_jsonl(tmp_path: Path) -> None:
    assert PATH_EARLY_A_NAME in FORBIDDEN_WRITE_NAMES
    assert PATH_EARLY_B_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathUnrealK3ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_A_NAME)
    with pytest.raises(PathUnrealK3ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / PATH_EARLY_B_NAME)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    assert INIT_ZIP_NAME in FORBIDDEN_WRITE_NAMES
    with pytest.raises(PathUnrealK3ProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / INIT_ZIP_NAME)


def test_license_split_family_is_path_exit_p_k3_unreal_red() -> None:
    flags = {
        "tag": "S_SPLIT",
        "winning_P": P_K3_UNREAL_RED,
        "S_MISSING_U": False,
        "S_THIN": False,
        "S_MISSING_PATH": False,
    }
    licensed = license_from_ab_k3(flags, flags)
    assert licensed["tag"] == "S_SPLIT"
    assert licensed["winning_P"] == P_K3_UNREAL_RED
    assert licensed["licensed_next_family"] == FAMILY_PATH_EXIT_P_K3_UNREAL_RED
    assert licensed["licensed_next_family"] == "PATH_EXIT:P_K3_UNREAL_RED"


def test_license_none_is_h_none_not_open_decision() -> None:
    flags = {
        "tag": "S_NONE",
        "winning_P": "none",
        "S_MISSING_U": False,
        "S_THIN": False,
        "S_MISSING_PATH": False,
    }
    licensed = license_from_ab_k3(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE
    assert licensed["licensed_next_family"] != "OPEN_DECISION"
    missing = {
        "tag": "S_MISSING",
        "winning_P": "none",
        "S_MISSING_U": True,
        "S_THIN": False,
        "S_MISSING_PATH": False,
    }
    licensed_m = license_from_ab_k3(missing, flags)
    assert licensed_m["licensed_next_family"] == FAMILY_H_NONE
    assert "OPEN_DECISION" not in licensed_m.values()


def test_s_multi_unreachable_with_one_candidate() -> None:
    assert len(CANDIDATE_NAMES) == 1
    rows = _split_k3_unreal(
        n_h_red=40,
        n_h_ok=10,
        n_w_red=6,
        n_w_ok=24,
        n_other_red=4,
        n_other_ok=16,
        also_k5=True,
        also_mae=True,
    )
    flags = compute_path_unreal_k3_flags(rows)
    assert list(flags["candidates"]) == [P_K3_UNREAL_RED]
    assert flags["tag"] != TAG_S_MULTI
    licensed = license_from_ab_k3(flags, flags)
    assert licensed["tag"] != TAG_S_MULTI
    src = Path("lumina_core/birth/awakening_path_unreal_k3_flags.py").read_text(encoding="utf-8")
    assert 'tag": TAG_S_MULTI' not in src
    assert 'tag": "S_MULTI"' not in src


def test_s_split_true_lift_060() -> None:
    rows = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=6, n_w_ok=24, n_other_red=4, n_other_ok=16
    )
    flags = compute_path_unreal_k3_flags(rows)
    assert flags["U_3"]["n_Hk"] == 50
    assert flags["U_3"]["n_Wk"] == 30
    cand = flags["candidates"][P_K3_UNREAL_RED]
    assert cand["lift"] == pytest.approx(0.60)
    assert cand["S_SPLIT"] is True
    assert flags["tag"] == "S_SPLIT"
    assert flags["winning_P"] == P_K3_UNREAL_RED
    assert flags["gate1"] == "NONE"


def test_s_split_false_lift_013() -> None:
    rows = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=20, n_w_ok=10, n_other_red=0, n_other_ok=20
    )
    flags = compute_path_unreal_k3_flags(rows)
    cand = flags["candidates"][P_K3_UNREAL_RED]
    assert cand["lift"] == pytest.approx(0.8 - (20.0 / 30.0))
    assert cand["S_SPLIT"] is False
    assert flags["tag"] == "S_NONE"
    assert flags["winning_P"] == "none"


def test_s_harm_true() -> None:
    rows = _split_k3_unreal(
        n_h_red=10, n_h_ok=40, n_w_red=20, n_w_ok=10, n_other_red=20, n_other_ok=0
    )
    flags = compute_path_unreal_k3_flags(rows)
    cand = flags["candidates"][P_K3_UNREAL_RED]
    assert cand["S_HARM"] is True
    assert cand["S_SPLIT"] is False
    assert flags["winning_P"] == "none"


def test_s_thin_n_h_30() -> None:
    rows = _split_k3_unreal(
        n_h_red=20, n_h_ok=10, n_w_red=6, n_w_ok=8, n_other_red=20, n_other_ok=20
    )
    flags = compute_path_unreal_k3_flags(rows)
    assert flags["U_3"]["n_Hk"] == 30
    assert flags["S_THIN"] is True
    assert flags["candidates"][P_K3_UNREAL_RED]["S_SPLIT"] is False
    assert flags["tag"] == "S_THIN"
    licensed = license_from_ab_k3(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE


def test_s_missing_path() -> None:
    rows = [_row(bars_held=8) for _ in range(80)]
    for i in range(25):
        rows[i]["close_reason"] = "target"
        rows[i]["trade_r"] = 1.21
    flags = compute_path_unreal_k3_flags(rows)
    assert flags["S_MISSING_PATH"] is True
    assert flags["tag"] == "S_MISSING"
    licensed = license_from_ab_k3(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE


def test_s_ab_disagree() -> None:
    rows_a = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=6, n_w_ok=24, n_other_red=4, n_other_ok=16
    )
    flags_a = compute_path_unreal_k3_flags(rows_a)
    rows_b = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=20, n_w_ok=10, n_other_red=0, n_other_ok=20
    )
    flags_b = compute_path_unreal_k3_flags(rows_b)
    assert flags_a["tag"] == "S_SPLIT"
    assert flags_b["tag"] != "S_SPLIT"
    licensed = license_from_ab_k3(flags_a, flags_b)
    assert licensed["tag"] == "S_AB_DISAGREE"
    assert licensed["winning_P"] == "none"
    assert licensed["licensed_next_family"] == FAMILY_H_NONE


def test_median_u3_does_not_use_hw_labels() -> None:
    rows = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=6, n_w_ok=24, n_other_red=4, n_other_ok=16
    )
    from lumina_core.birth.awakening_edge import policy_only_rows
    from lumina_core.birth.awakening_open_split_flags import universe_rows

    universe = universe_rows(policy_only_rows(rows))
    u_3 = universe_k(universe, 3)
    thr = compute_k_medians(u_3, 3)
    flipped = []
    for row in universe:
        copy = dict(row)
        if copy.get("close_reason") == "stop":
            copy["close_reason"] = "target"
            copy["trade_r"] = 1.21
        elif copy.get("close_reason") == "target":
            copy["close_reason"] = "stop"
            copy["trade_r"] = -1.04
        flipped.append(copy)
    thr_flip = compute_k_medians(universe_k(universe_rows(policy_only_rows(flipped)), 3), 3)
    assert thr["unreal_r"] == pytest.approx(thr_flip["unreal_r"] or 0.0)


def test_missing_unreal_not_imputed_zero() -> None:
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
            "bars_held": 8,
        }
    )
    assert "path_k3_unreal_r" not in row
    assert pred_unreal_red(row, k=3, threshold=0.0) is False
    flags = compute_path_unreal_k3_flags([_row(bars_held=8) for _ in range(80)])
    assert flags["S_MISSING_PATH"] is True
    cand = flags["candidates"][P_K3_UNREAL_RED]
    assert cand["threshold"] is None
    assert cand["n_defined"] == 0


def test_died_before_3_not_in_u3() -> None:
    dead = _row(bars_held=2, path_k3_unreal_r=-2.0)
    live = _row(bars_held=8, path_k3_unreal_r=-2.0)
    from lumina_core.birth.awakening_open_split_flags import universe_rows

    u_3 = universe_k(universe_rows([dead, live]), 3)
    assert len(u_3) == 1
    assert u_3[0]["bars_held"] == 8
    flags = compute_path_unreal_k3_flags(
        [dead] + [_row(bars_held=8, path_k3_unreal_r=-1.0) for _ in range(59)]
    )
    assert flags["n_died_before_3"] >= 1
    assert flags["U_3"]["n_Uk"] == 59


def test_flip_cannot_win() -> None:
    rows = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=6, n_w_ok=24, n_other_red=4, n_other_ok=16
    )
    flags = compute_path_unreal_k3_flags(rows)
    from lumina_core.birth.awakening_edge import policy_only_rows
    from lumina_core.birth.awakening_open_split_flags import hole_from_u, universe_rows, winners_from_u

    universe = universe_rows(policy_only_rows(rows))
    u_3 = universe_k(universe, 3)
    flipped = flip_row(
        u_3,
        hole_from_u(u_3),
        winners_from_u(u_3),
        s_missing_u=bool(flags.get("S_MISSING_U")),
        s_missing_path=bool(flags.get("S_MISSING_PATH")),
        s_thin_k=bool((flags.get("U_3") or {}).get("S_THIN")),
        medians=compute_k_medians(u_3, 3),
    )
    assert flipped["READ_ONLY_FLIP"] is True
    assert flipped["S_SPLIT"] is False
    t5 = table_t5(rows)
    assert t5[P_K3_UNREAL_RED]["READ_ONLY_FLIP"] is True
    assert t5[P_K3_UNREAL_RED]["S_SPLIT"] is False
    assert flags["winning_P"] != "FLIP"


def test_rescore_path_early_fixture_matches_locked_lift() -> None:
    path_a = Path("reports/birth_cloud_run/artifacts") / PATH_EARLY_A_NAME
    if not path_a.is_file():
        pytest.skip("path_early A JSONL not in CI artifacts")
    from lumina_core.birth.awakening_mech import load_close_jsonl
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    rows = load_close_jsonl(path_a)
    flags = compute_path_unreal_k3_flags(rows)
    assert flags["n_U"] == LOCKED_PATH_EARLY_A["n_U"] == 126
    assert flags["n_H"] == LOCKED_PATH_EARLY_A["n_H"]
    assert flags["n_W"] == LOCKED_PATH_EARLY_A["n_W"]
    assert flags["U_3"]["n_Uk"] == LOCKED_PATH_EARLY_A["n_Uk3"]
    assert flags["U_3"]["n_Hk"] == LOCKED_PATH_EARLY_A["n_Hk3"]
    assert flags["U_3"]["n_Wk"] == LOCKED_PATH_EARLY_A["n_Wk3"]
    cand = flags["candidates"][P_K3_UNREAL_RED]
    assert abs(float(cand["lift"]) - LOCKED_LIFT_A) <= 1e-9
    assert abs(float(cand["cov_H"]) - LOCKED_COV_H_A) <= 1e-9
    assert list(flags["candidates"]) == [P_K3_UNREAL_RED]
    _ = file_sha256(path_a)


def test_source_does_not_score_k5_as_candidate() -> None:
    src = Path("lumina_core/birth/awakening_path_unreal_k3_flags.py").read_text(encoding="utf-8")
    assert "P_K5_UNREAL_RED" not in src
    assert "P_K5_MAE_DEEP" not in src
    rows = _split_k3_unreal(
        n_h_red=40,
        n_h_ok=10,
        n_w_red=6,
        n_w_ok=24,
        n_other_red=4,
        n_other_ok=16,
        also_k5=True,
    )
    flags = compute_path_unreal_k3_flags(rows)
    assert "P_K5_UNREAL_RED" not in flags["candidates"]
    assert list(flags["candidates"]) == [P_K3_UNREAL_RED]


def test_source_does_not_score_mae_as_candidate() -> None:
    src = Path("lumina_core/birth/awakening_path_unreal_k3_flags.py").read_text(encoding="utf-8")
    assert "P_K3_MAE_DEEP" not in src
    rows = _split_k3_unreal(
        n_h_red=40,
        n_h_ok=10,
        n_w_red=6,
        n_w_ok=24,
        n_other_red=4,
        n_other_ok=16,
        also_mae=True,
    )
    flags = compute_path_unreal_k3_flags(rows)
    assert "P_K3_MAE_DEEP" not in flags["candidates"]
    assert flags["winning_P"] in {P_K3_UNREAL_RED, "none"}


def test_predicates_do_not_use_close_mae_r() -> None:
    for rel in (
        "lumina_core/birth/awakening_path_unreal_k3.py",
        "lumina_core/birth/awakening_path_unreal_k3_flags.py",
        "lumina_core/birth/awakening_path_unreal_k3_run.py",
        "lumina_core/birth/awakening_path_unreal_k3_eval.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert re.search(r'row\.get\([\'"]mae_r', src) is None
        assert re.search(r'\[[\'"]mae_r[\'"]\]', src) is None
        assert re.search(r'row\.get\([\'"]mfe_r', src) is None
        assert "pred_mae_deep" not in src


def test_default_prefers_rescore_when_keys_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_unreal_k3_run as run_mod
    from lumina_core.birth.awakening_path_unreal_k3_run import run_path_unreal_k3

    artifacts = tmp_path / "artifacts"
    artifacts.mkdir(parents=True)
    rows = _split_k3_unreal(
        n_h_red=40, n_h_ok=10, n_w_red=6, n_w_ok=24, n_other_red=4, n_other_ok=16
    )
    (artifacts / PATH_EARLY_A_NAME).write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (artifacts / PATH_EARLY_B_NAME).write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )

    def _boom(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("replay must not run when path_k3_unreal_r is present")

    monkeypatch.setattr(run_mod, "replay_path_unreal_k3", _boom)
    monkeypatch.setattr(run_mod, "run_path_unreal_k3_eval_leg", _boom)
    out = run_path_unreal_k3(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert out["replay_ran"] is False
    assert out["source"] == "path_early_jsonl"
    assert out["skip_replay"] is False
    flags = json.loads((tmp_path / "artifacts" / "path_unreal_k3_flags.json").read_text(encoding="utf-8"))
    assert flags["source"] == "path_early_jsonl"
    assert flags["replay_ran"] is False
    assert list(flags["A"]["candidates"]) == [P_K3_UNREAL_RED]


def test_skip_replay_without_source_is_inconclusive(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_unreal_k3_run import run_path_unreal_k3

    out = run_path_unreal_k3(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert out["overall"] == OVERALL_INCONCLUSIVE
    assert out["skip_replay"] is True
    assert out["replay_ran"] is False
    flags = json.loads((tmp_path / "artifacts" / "path_unreal_k3_flags.json").read_text(encoding="utf-8"))
    assert flags["overall"] == OVERALL_INCONCLUSIVE
    assert overall_path_unreal_k3_string(skip_replay=True, source_jsonl_present=False) == OVERALL_INCONCLUSIVE


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
    with pytest.raises(PathUnrealK3ProtocolError, match="train seed"):
        assert_eval_seed(TRAIN_SEED)
    assert TRAIN is False
    for rel in (
        "lumina_core/birth/awakening_path_unreal_k3_run.py",
        "lumina_core/birth/awakening_path_unreal_k3_eval.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "model.learn(" not in src
    assert honesty_paragraph(source="path_early_jsonl").count("P_K3_UNREAL_RED") >= 1
    assert OVERALL_MEASURE.endswith("PATH_MEASURE_ONLY")
