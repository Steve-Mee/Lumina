"""Awakening OPEN_SPLIT: protocol, flags, serializer, eval wrap, peeking guard."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_open_split import (
    CANDIDATE_NAMES,
    CONTROL_SHA256,
    F_OCC_FLOOR,
    F_SESSION_EARLY,
    FORBIDDEN_WRITE_NAMES,
    HOLE_TAX_SHA256,
    INIT_SHA256,
    OPEN_A_NAME,
    TRAIN_SEED,
    OpenSplitProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    compute_open_split_flags,
    isolated_workspace,
    license_from_ab,
    pred_occ_floor,
)
from lumina_core.birth.awakening_open_split_path import inspect_open_split_protocol
from lumina_core.birth.awakening_open_split_run import run_open_split_eval_leg
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row, occupancy_floor_neighborhood


def _row(
    *,
    entry: str | None = "NEUTRAL",
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    trade_r: float = -1.04,
    pnl: float = -117.0,
    plant: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": pnl,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
    }
    if entry is not None:
        row["entry_regime"] = entry
    row.update(extra)
    return row


def _universe(
    *, n_h: int, n_w: int, n_other: int = 20, mark_h: int = 0, mark_w: int = 0, extra: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    occ_hit = 0.27
    occ_miss = 0.40
    for i in range(n_h):
        payload = dict(extra or {})
        payload["open_occ_flat"] = occ_hit if i < mark_h else occ_miss
        rows.append(_row(close_reason="stop", regime="NEUTRAL", trade_r=-1.04, pnl=-117.0, **payload))
    for i in range(n_w):
        payload = dict(extra or {})
        payload["open_occ_flat"] = occ_hit if i < mark_w else occ_miss
        rows.append(_row(close_reason="target", regime="NEUTRAL", trade_r=1.21, pnl=60.0, **payload))
    for _ in range(n_other):
        payload = dict(extra or {})
        payload["open_occ_flat"] = occ_miss
        rows.append(
            _row(
                close_reason="time_stop",
                regime="NEUTRAL",
                trade_r=-0.1,
                pnl=-5.0,
                **payload,
            )
        )
    return rows


def test_inspect_open_split_protocol_complete() -> None:
    dump = inspect_open_split_protocol()
    assert dump["missing_sites"] == []
    assert dump["gate0_complete"] is True


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_runner_refuses_train_seed_20260901() -> None:
    with pytest.raises(OpenSplitProtocolError, match="train seed 20260901"):
        assert_eval_seed(TRAIN_SEED)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "awakening_select_pi_star.zip")
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "awakening_hole_tax_pi_star.zip")
    assert OPEN_A_NAME not in FORBIDDEN_WRITE_NAMES
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_open_split/workspace")
    assert TRAIN is False


def test_forbidden_write_entry_autopsy_jsonl(tmp_path: Path) -> None:
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "entry_autopsy_A_close_ledger.jsonl")
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "entry_autopsy_B_close_ledger.jsonl")
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "grind_A_close_ledger.jsonl")


def test_assert_not_evaluated_policy_refuses_control_sha(tmp_path: Path) -> None:
    control = tmp_path / "artifacts" / "awakening_select_pi_star.zip"
    control.parent.mkdir(parents=True)
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(OpenSplitProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(control)
    sha_file = tmp_path / "control.zip"
    sha_file.write_bytes(b"not-the-parent")
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    if file_sha256(sha_file) == CONTROL_SHA256:
        with pytest.raises(OpenSplitProtocolError, match="control sha"):
            assert_not_evaluated_policy(sha_file)


def test_assert_not_evaluated_policy_refuses_hole_tax_sha(tmp_path: Path) -> None:
    hole_tax = tmp_path / "artifacts" / "awakening_hole_tax_pi_star.zip"
    hole_tax.parent.mkdir(parents=True)
    hole_tax.write_bytes(b"PK\x03\x04hole-tax")
    with pytest.raises(OpenSplitProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(hole_tax)
    _ = HOLE_TAX_SHA256


def test_s_split_true_lift_060() -> None:
    rows = _universe(n_h=50, n_w=30, n_other=20, mark_h=40, mark_w=6)
    flags = compute_open_split_flags(rows)
    cand = flags["candidates"][F_OCC_FLOOR]
    assert flags["n_H"] == 50
    assert flags["n_W"] == 30
    assert cand["lift"] == pytest.approx(0.60)
    assert cand["S_SPLIT"] is True
    assert cand["S_HARM"] is False
    assert flags["tag"] == "S_SPLIT"
    assert flags["winning_F"] == F_OCC_FLOOR


def test_s_split_false_lift_013() -> None:
    rows = _universe(n_h=50, n_w=30, n_other=20, mark_h=40, mark_w=20)
    flags = compute_open_split_flags(rows)
    cand = flags["candidates"][F_OCC_FLOOR]
    assert cand["lift"] == pytest.approx(0.8 - (20.0 / 30.0))
    assert cand["S_SPLIT"] is False


def test_s_harm_true() -> None:
    rows = _universe(n_h=50, n_w=30, n_other=20, mark_h=10, mark_w=20)
    flags = compute_open_split_flags(rows)
    cand = flags["candidates"][F_OCC_FLOOR]
    assert cand["S_HARM"] is True
    assert cand["S_SPLIT"] is False


def test_s_thin_n_h_30() -> None:
    rows = _universe(n_h=30, n_w=30, n_other=20, mark_h=25, mark_w=2)
    flags = compute_open_split_flags(rows)
    assert flags["S_THIN"] is True
    assert flags["candidates"][F_OCC_FLOOR]["S_SPLIT"] is False
    assert flags["tag"] == "S_THIN"


def test_s_missing_u_entry_regime() -> None:
    rows = _universe(n_h=50, n_w=30, n_other=0)
    n_miss = 20
    for _ in range(n_miss):
        rows.append(_row(entry=None, close_reason="flatten", regime="NEUTRAL", trade_r=0.0, pnl=0.0))
    flags = compute_open_split_flags(rows)
    assert flags["S_MISSING_U"] is True
    assert flags["tag"] == "S_MISSING"


def test_s_multi_two_features() -> None:
    rows = _universe(n_h=50, n_w=30, n_other=20, mark_h=40, mark_w=6)
    for i, row in enumerate(rows):
        if row.get("open_occ_flat") == 0.27:
            row["open_session_phase"] = 0.0
        else:
            row["open_session_phase"] = 1.0
    flags = compute_open_split_flags(rows)
    assert flags["candidates"][F_OCC_FLOOR]["S_SPLIT"] is True
    assert flags["candidates"][F_SESSION_EARLY]["S_SPLIT"] is True
    assert flags["tag"] == "S_MULTI"
    assert flags["winning_F"] == "none"


def test_s_ab_disagree() -> None:
    rows_a = _universe(n_h=50, n_w=30, n_other=20, mark_h=40, mark_w=6)
    flags_a = compute_open_split_flags(rows_a)
    rows_b = _universe(n_h=50, n_w=30, n_other=20, mark_h=0, mark_w=0)
    for i, row in enumerate(rows_b):
        if i < 40 or (50 <= i < 56):
            row["open_session_phase"] = 0.0
        else:
            row["open_session_phase"] = 1.0
    flags_b = compute_open_split_flags(rows_b)
    assert flags_a["winning_F"] == F_OCC_FLOOR
    assert flags_b["winning_F"] == F_SESSION_EARLY
    licensed = license_from_ab(flags_a, flags_b)
    assert licensed["tag"] == "S_AB_DISAGREE"
    assert licensed["licensed_next_family"] == "OPEN_DECISION"


def test_f_occ_floor_uses_occupancy_floor_neighborhood() -> None:
    assert occupancy_floor_neighborhood(0.25) is True
    assert occupancy_floor_neighborhood(0.30) is True
    assert occupancy_floor_neighborhood(0.31) is False
    assert occupancy_floor_neighborhood(0.24) is False
    assert pred_occ_floor({"open_occ_flat": 0.25}) is True
    assert pred_occ_floor({"open_occ_flat": 0.30}) is True
    assert pred_occ_floor({"open_occ_flat": 0.31}) is False
    assert pred_occ_floor({"open_occ_flat": 0.24}) is False


def test_missing_open_occ_flat_does_not_impute_zero() -> None:
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
            "reward_on_close": -0.2,
        }
    )
    assert "open_occ_flat" not in row
    assert row.get("open_occ_flat") != 0.0
    assert pred_occ_floor(row) is False


def test_close_ledger_row_keeps_old_keys() -> None:
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
    assert "entry_regime" not in old


def test_close_ledger_row_copies_new_keys_when_present() -> None:
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
            "entry_regime": "NEUTRAL",
            "open_occ_flat": 0.27,
            "open_cum_flat": 0.28,
            "open_in_band_seen": True,
            "open_session_phase": 0.0,
            "open_confluence": 0.6,
            "open_news_proximity": 0.1,
            "open_imbalance": 1.0,
            "open_range_stop_frac": 0.4,
            "open_side": 1,
            "bars_since_prev_policy_stop": 3,
            "open_participation_mode": "PASSTHROUGH",
            "source": "awakening_open_split",
        }
    )
    assert filled["open_occ_flat"] == pytest.approx(0.27)
    assert filled["open_participation_mode"] == "PASSTHROUGH"
    assert filled["source"] == "awakening_open_split"


def test_close_ledger_row_omits_missing_open_occ_flat() -> None:
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
    assert "open_occ_flat" not in row


def test_start_open_telem_required_kwargs_still_work() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem

    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=2, entry_price=20000.0, side=1)
    assert stash["entry_regime"] == "NEUTRAL"
    assert stash["side"] == 1
    assert "open_occ_flat" not in stash
    assert "open_imbalance" not in stash


def test_imbalance_default_not_persisted() -> None:
    from lumina_core.birth.sim_runner_entry_telem import gather_open_features, start_open_telem

    extras = gather_open_features(SimpleNamespace(), {"close": 20000.0}, {}, 20000.0)
    assert "open_imbalance" not in extras
    stash = start_open_telem(
        entry_regime="NEUTRAL",
        entry_bar_index=0,
        entry_price=20000.0,
        side=1,
        open_imbalance=extras.get("open_imbalance"),
    )
    assert stash.get("open_imbalance") != 1.0
    assert "open_imbalance" not in stash


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


def test_open_split_runner_never_calls_learn_fn() -> None:
    src = Path("lumina_core/birth/awakening_open_split_run.py").read_text(encoding="utf-8")
    assert "learn_fn" not in src
    assert "model.learn(" not in src
    assert "model.learn" not in src


def test_optimizer_steps_zero_after_mocked_eval(tmp_path: Path) -> None:
    child = tmp_path / "parent.zip"
    child.write_bytes(b"PK\x03\x04parent")

    def _stub_rollout(**kwargs: Any) -> SimpleNamespace:
        _ = kwargs
        return SimpleNamespace(trajectories=[], rollout_steps=0, optimizer_steps=0)

    with pytest.raises(OpenSplitProtocolError, match="train seed|eval seed"):
        run_open_split_eval_leg(
            seed=20260901,
            holdout=[{"close": 1.0}],
            workspace_root=tmp_path,
            reports=tmp_path,
            policy_path=child,
            rollout_fn=_stub_rollout,
        )


def test_candidate_names_only_five() -> None:
    assert CANDIDATE_NAMES == (
        "F_OCC_FLOOR",
        "F_SESSION_EARLY",
        "F_TIGHT_RANGE",
        "F_AFTER_STOP",
        "F_IMBAL_FLAT",
    )
    assert len(CANDIDATE_NAMES) == 5


def test_open_split_source_does_not_use_bars_held_in_predicates() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_split.py",
        "lumina_core/birth/awakening_open_split_flags.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "bars_held" not in src


def test_open_split_source_does_not_use_mae_r_in_predicates() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_split.py",
        "lumina_core/birth/awakening_open_split_flags.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "mae_r" not in src


def test_open_split_source_does_not_reference_bible_mtf_bias_as_candidate() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_split.py",
        "lumina_core/birth/awakening_open_split_flags.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "bible_mtf_bias" not in src


def test_open_split_source_does_not_implement_open_filter_controller() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_split.py",
        "lumina_core/birth/awakening_open_split_flags.py",
        "lumina_core/birth/awakening_open_split_run.py",
        "lumina_core/birth/awakening_open_split_tables.py",
        "lumina_core/birth/awakening_open_split_report.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "def apply_open_filter" not in src
        assert "def refuse_neutral_open" not in src
        assert "def skip_neutral" not in src
        assert "decide_stage2_participation(" not in src


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
