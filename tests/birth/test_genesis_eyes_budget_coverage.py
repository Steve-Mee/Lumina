"""Coverage for GENESIS_EYES_BUDGET protocol, eval helpers, and orchestrator."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from lumina_core.birth.genesis_eyes_budget import (
    STUDENT_BIRTH_NAME,
    STUDENT_BIRTH_SHA256,
    STUDENT_EYES_NAME,
    BudgetProtocolError,
    assert_budget_fixture,
    assert_g5_ledgers_untouched,
    budget_fixture_spec,
    copy_frozen_students,
    g5_ledger_fingerprints,
    persist_budget_fixture,
    prepare_budget_trees,
    refuse_forbidden_zip,
    refuse_this_tape_hash,
    write_bytes_sha,
)
from lumina_core.birth.genesis_eyes_budget_eval import (
    eval_budget_leg,
    organism_stats,
    policy_obs_dim,
    run_budget_eval,
)
from lumina_core.birth.genesis_eyes_budget_report import render_audit, render_verdict
from lumina_core.birth.genesis_eyes_budget_run import _append_logs, _git, _write_json, run_genesis_eyes_budget
from lumina_core.birth.genesis_eyes_budget_tables import table_t0_identity, table_t1_honesty, table_t2_leg, table_t3_license
from lumina_core.birth.purged_split import PurgedSplit


@pytest.mark.unit
def test_refuse_zip_and_empty_hash() -> None:
    assert refuse_this_tape_hash("") == ""
    refuse_forbidden_zip("student_birth_exit_pi_star.zip", STUDENT_BIRTH_SHA256)
    with pytest.raises(BudgetProtocolError, match="dead zip name"):
        refuse_forbidden_zip("birth_exit_pi_star.zip", "00" * 32)
    with pytest.raises(BudgetProtocolError, match="dead zip sha"):
        refuse_forbidden_zip("student_x.zip", "8cc435c6" + "ab" * 28)


@pytest.mark.unit
def test_copy_students_and_g5_fingerprint(tmp_path: Path) -> None:
    if not Path("reports/genesis_cloud_run/artifacts/genesis_birth_exit_pi_star.zip").is_file():
        pytest.skip("origin student zip missing")
    out = copy_frozen_students(tmp_path)
    assert out["student_birth_sha256"] == STUDENT_BIRTH_SHA256
    assert (tmp_path / STUDENT_BIRTH_NAME).is_file()
    assert (tmp_path / f"{STUDENT_BIRTH_NAME}.sha256").is_file()
    prints = g5_ledger_fingerprints()
    assert_g5_ledgers_untouched(prints)
    with pytest.raises(BudgetProtocolError, match="overwritten"):
        assert_g5_ledgers_untouched({next(iter(prints)): "deadbeef"})


@pytest.mark.unit
def test_fixture_spec_and_assert(tmp_path: Path) -> None:
    spec = budget_fixture_spec(holdout_pct=0.40)
    assert spec.seed == 20260905
    assert spec.holdout_pct == 0.40
    assert spec.start_et is not None and spec.start_et.year == 2026
    with pytest.raises(BudgetProtocolError, match="source"):
        assert_budget_fixture(tmp_path, {"source": "real"})
    with pytest.raises(BudgetProtocolError, match="0.0"):
        assert_budget_fixture(tmp_path, {"source": "synthetic_cloud_fixture", "real_data_pct": 1.0})
    with pytest.raises(BudgetProtocolError, match="80k"):
        assert_budget_fixture(
            tmp_path,
            {
                "source": "synthetic_cloud_fixture",
                "real_data_pct": 0.0,
                "host_real_data_pct": 0.0,
                "hash": "abc123def4567890",
                "holdout_tick_count": 10,
                "holdout_regimes": ["NEUTRAL", "TREND_UP", "TREND_DOWN"],
                "ticks_per_leg": [5, 5],
            },
        )


@pytest.mark.unit
def test_persist_budget_fixture_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "work"
    art = tmp_path / "art"
    work.mkdir()
    art.mkdir()
    (work / "state").mkdir()
    ticks = [{"source": "synthetic_cloud_fixture", "timestamp": "t"}]
    holdout = [{"source": "synthetic_cloud_fixture"}] * 80_000
    train = [{"source": "synthetic_cloud_fixture"}] * 10
    manifest = {
        "source": "synthetic_cloud_fixture",
        "hash": "abc123def4567890",
        "holdout_tick_count": 80_000,
        "holdout_pct": 0.40,
        "holdout_regimes": ["NEUTRAL", "TREND_UP", "TREND_DOWN"],
        "tick_count": 90_000,
    }
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget.persist_cloud_fixture",
        lambda work, spec=None: SimpleNamespace(fixture_manifest=dict(manifest)),
    )
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget.load_ticks_cache", lambda _w: ticks)
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget.load_split_cache",
        lambda _w, holdout_pct=0.4: PurgedSplit(train=train, holdout=holdout, holdout_days=10, train_days=20),
    )
    payload = persist_budget_fixture(work, art)
    assert payload["fixture_seed"] == 20260905
    assert (art / "01_budget_fixture_manifest.json").is_file()


@pytest.mark.unit
def test_prepare_trees_and_write_sha(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    src = Path("config.yaml")
    if not src.is_file():
        pytest.skip("config.yaml missing")
    (repo / "config.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    reports, work, art = prepare_budget_trees(repo=repo)
    assert (work / "config.yaml").is_file()
    assert reports.name == "genesis_budget_run"
    blob = art / "x.bin"
    blob.write_bytes(b"abc")
    digest = write_bytes_sha(blob)
    assert len(digest) == 64


@pytest.mark.unit
def test_eval_helpers_and_missing_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert policy_obs_dim(SimpleNamespace()) == -1
    assert policy_obs_dim(SimpleNamespace(observation_space=SimpleNamespace(shape=(43,)))) == 43
    empty = organism_stats([])
    assert empty["n_policy"] == 0
    rows = [
        {
            "plant": False,
            "plant_entry": False,
            "force_open": False,
            "trade_r": -0.2,
            "bars_held": 10,
            "u_tag": True,
            "h_tag": True,
        }
    ]
    stats = organism_stats(rows)
    assert "n_policy" in stats
    with pytest.raises(BudgetProtocolError, match="A/B only"):
        eval_budget_leg(
            holdout=[], work=tmp_path, art=tmp_path, zip_path=tmp_path / STUDENT_BIRTH_NAME,
            organism="birth", leg="C", expected_dim=43,
        )
    missing = run_budget_eval(work=tmp_path, art=tmp_path, holdout_pct=0.40)
    assert missing["S_MISSING"] is True
    assert missing["reason"] == "holdout_missing"
    zip_path = tmp_path / STUDENT_BIRTH_NAME
    zip_path.write_bytes(b"not-a-zip")
    out = eval_budget_leg(
        holdout=[{}], work=tmp_path, art=tmp_path, zip_path=zip_path,
        organism="birth", leg="A", expected_dim=43,
    )
    assert out["S_MISSING"] is True
    dummy = SimpleNamespace(observation_space=SimpleNamespace(shape=(46,)))
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_eval.load_frozen_policy", lambda _p: dummy)
    dim_miss = eval_budget_leg(
        holdout=[{}], work=tmp_path, art=tmp_path, zip_path=zip_path,
        organism="birth", leg="A", expected_dim=43,
    )
    assert dim_miss["S_MISSING"] is True
    assert "obs_dim" in str(dim_miss.get("reason"))


@pytest.mark.unit
def test_eval_leg_success_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zip_path = tmp_path / STUDENT_EYES_NAME
    zip_path.write_bytes(b"zip")
    dummy = SimpleNamespace(observation_space=SimpleNamespace(shape=(46,)))

    def _rollout(**kwargs: Any) -> None:
        Path(kwargs["ledger_path"]).write_text(
            '{"plant":false,"force_open":false,"trade_r":-0.1,"bars_held":90}\n',
            encoding="utf-8",
        )

    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_eval.load_frozen_policy", lambda _p: dummy)
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_eval.run_evaluate_only", _rollout)
    out = eval_budget_leg(
        holdout=[{}, {}], work=tmp_path, art=tmp_path, zip_path=zip_path,
        organism="eyes", leg="B", expected_dim=46,
    )
    assert out["S_MISSING"] is False
    assert out["obs_dim"] == 46
    assert (tmp_path / "budget_eyes_B_close_ledger.sha256").is_file()


@pytest.mark.unit
def test_run_budget_eval_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    holdout = [{"i": i} for i in range(4)]
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_eval.load_split_cache",
        lambda _w, holdout_pct=0.4: PurgedSplit(train=[], holdout=holdout, holdout_days=1, train_days=1),
    )
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_eval.eval_budget_leg",
        lambda **kw: {"n_policy": 0, "S_MISSING": True, "reason": "zip_unloadable"},
    )
    out = run_budget_eval(work=tmp_path, art=tmp_path, holdout_pct=0.40)
    assert out["S_MISSING"] is True
    assert "zip_unloadable" in out["reason"]
    assert out["eval_seeds"] == ["A", "B"]
    assert out["learn_called"] is False


@pytest.mark.unit
def test_orchestrator_s_missing_and_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_run.copy_frozen_students",
        lambda _art: {"student_birth_sha256": STUDENT_BIRTH_SHA256, "student_eyes_sha256": "a" * 64},
    )
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_run.persist_budget_fixture",
        MagicMock(side_effect=BudgetProtocolError("holdout < 80k after one holdout_pct raise")),
    )
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.BUDGET_ROOT", repo / "reports" / "genesis_budget_run")
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.REPO_ROOT", repo)
    flags = run_genesis_eyes_budget(repo=repo)
    assert flags["tag"] == "S_MISSING"
    assert flags["GENESIS_EYES_OK"] is False
    assert flags["learn_called"] is False
    assert flags["REAL"] == "no"
    reports = repo / "reports" / "genesis_budget_run"
    assert (reports / "GENESIS_EYES_BUDGET_VERDICT.md").is_file()
    assert (reports / "artifacts" / "genesis_eyes_budget_flags.json").is_file()


@pytest.mark.unit
def test_orchestrator_budget_ok_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    birth = {"n_policy": 160, "n_H": 80, "mean_r": -0.20, "wr": 0.3, "n_W": 20, "bars_held_p50": 12.0}
    child = {"n_policy": 160, "n_H": 40, "mean_r": -0.10, "wr": 0.4, "n_W": 30, "bars_held_p50": 90.0}
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_run.copy_frozen_students",
        lambda _art: {"student_birth_sha256": STUDENT_BIRTH_SHA256, "student_eyes_sha256": "a9ffa852" + "0" * 56},
    )
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_run.persist_budget_fixture",
        lambda _w, _a: {
            "hash": "e963d1ce7d726ebf",
            "holdout_tick_count": 86460,
            "ticks_per_leg": [43230, 43230],
            "holdout_pct": 0.40,
            "real_data_pct": 0.0,
            "source": "synthetic_cloud_fixture",
        },
    )
    monkeypatch.setattr(
        "lumina_core.birth.genesis_eyes_budget_run.run_budget_eval",
        lambda **_k: {
            "birth_A": birth, "birth_B": birth, "eyes_A": child, "eyes_B": child,
            "S_MISSING": False, "reason": "", "ticks_per_leg": [43230, 43230],
        },
    )
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.BUDGET_ROOT", repo / "reports" / "genesis_budget_run")
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.REPO_ROOT", repo)
    flags = run_genesis_eyes_budget(repo=repo)
    assert flags["tag"] == "BUDGET_OK"
    assert flags["HOLE_MOVED_A"] is True
    assert flags["HOLE_MOVED_B"] is True
    assert flags["GENESIS_EYES_OK"] is False


@pytest.mark.unit
def test_tables_report_git_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _git("HEAD")
    assert _git("not-a-real-ref-zzzz") == ""
    _write_json(tmp_path / "x.json", {"a": 1})
    t0 = table_t0_identity(origin_main="abc", train_hash="e963", birth_sha="d3", eyes_sha="a9")
    t1 = table_t1_honesty()
    t2 = table_t2_leg("A", {"n_policy_birth": 150, "n_policy_child": 150, "HOLE_MOVED": True})
    t3 = table_t3_license({"tag": "BUDGET_OK", "law": "SHADOW", "licensed_next_family": "AWAKENING_MARK_EYES"})
    audit = render_audit(gate0={}, proto={}, t0=t0, t1=t1, t2_a=t2, t2_b=t2, t3=t3, flags={"tag": "BUDGET_OK"}, g6={})
    verdict = render_verdict(flags={"tag": "BUDGET_OK", "GENESIS_EYES_OK": False}, t2_a=t2, t2_b=t2)
    assert "BUDGET_OK" in audit and "BUDGET_OK" in verdict
    assert t1["pct_synthetic_cloud_fixture"] == 0.0
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.BUDGET_ROOT", tmp_path)
    monkeypatch.setattr("lumina_core.birth.genesis_eyes_budget_run.REPO_ROOT", tmp_path)
    _append_logs({"tag": "BUDGET_OK", "law": "SHADOW", "licensed_next_family": "AWAKENING_MARK_EYES"})
    assert (tmp_path / "LUMINA_GENESIS_BUDGET_EXPERIMENT_LOG.md").is_file()
