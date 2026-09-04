"""Coverage for OBJECTIVE_TRADE run/eval/train/tables/report/tape. No 10k learn()."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from lumina_core.config_loader import ConfigLoader

from lumina_core.birth.awakening_obj_eval import (
    organism_stats,
    policy_obs_dim,
    run_obj_eval,
)
from lumina_core.birth.awakening_obj_flags import TAG_OBJ_THIN, TAG_S_MISSING
from lumina_core.birth.awakening_obj_report import render_audit, render_verdict
from lumina_core.birth.awakening_obj_run import (
    POINTER,
    assert_origin_untouched,
    body_exam_enabled,
    origin_guard_paths,
    snapshot_origin_artifacts,
)
from lumina_core.birth.awakening_obj_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_obj_tape import (
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    OBJ_SEED,
    ObjProtocolError,
    assert_forbidden_init,
    inspect_obj_protocol,
    load_obj_train_split,
    refuse_this_tape_hash,
)
from lumina_core.birth.awakening_obj_train import pin_train_seed, run_obj_v1_train
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW


@pytest.fixture(autouse=True)
def _isolate_obj_process_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Coverage Report is sequential: do not leak stub LUMINA_CONFIG into later suites."""
    monkeypatch.setenv("LUMINA_CONFIG", os.environ.get("LUMINA_CONFIG", "config.yaml"))
    monkeypatch.setenv("LUMINA_FABRIC_SUPERVISOR", os.environ.get("LUMINA_FABRIC_SUPERVISOR", "0"))
    monkeypatch.setenv("VOICE_ENABLED", os.environ.get("VOICE_ENABLED", "false"))
    yield
    ConfigLoader.invalidate()


def _book(*, n_policy: int = 0, mean_r: float = 0.0, n_h: int = 0) -> dict[str, Any]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": 0.0, "n_W": 0, "bars_held_p50": 0.0}


def _fixture(**extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "world_ok": True,
        "real_data_pct": 0.0,
        "hash": "3930475515f9576a",
        "phase_blocks": 6,
        "gen_up": 10,
        "gen_down": 10,
        "gen_range": 10,
        "train_up_frac": 0.29,
        "train_down_frac": 0.29,
        "hold_up_frac": 0.28,
        "hold_down_frac": 0.28,
        "source": "synthetic_cloud_fixture",
    }
    payload.update(extra)
    return payload


def _eval_ok() -> dict[str, Any]:
    book = {**_book(), "S_MISSING": False}
    return {"A": book, "B": book, "S_MISSING": False, "both_loaded": True, "reason": ""}


def test_coverage_inspect_complete() -> None:
    dump = inspect_obj_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    assert OBJ_SEED == 20260913


def test_coverage_tables_report_and_tape_guards(tmp_path: Path) -> None:
    t0 = table_t0_identity(origin_main="abc", train_hash="39304755", baseline_sha="a9ffa852", child_sha="")
    t1 = table_t1_honesty()
    t2 = table_t2_leg("A", {"n_policy_base": 0, "MOVED": False, "S_THIN": True})
    t3 = table_t3_license({"tag": TAG_OBJ_THIN, "law": "NONE"})
    assert t0["prod_enricher_default_changed"] is False
    assert t0["train_force_open"] is True
    assert t0["eval_force_open"] is False
    assert t1["G6_tag"] == "REAL_DOOR_LOCKED"
    assert t2["leg"] == "A"
    assert t3["GENESIS_EYES_OK"] is False
    assert t3["floor_waived"] is False
    flags = {
        "tag": TAG_OBJ_THIN,
        "law": "NONE",
        "licensed_next_family": "H_NONE",
        "GENESIS_EYES_OK": False,
        "world_ok": True,
        "train_force_open": True,
        "eval_force_open": False,
        "floor_waived": False,
        "REAL": "no",
        "G6_tag": "REAL_DOOR_LOCKED",
    }
    audit = render_audit(gate0={}, proto={}, t0=t0, t1=t1, t2_a=t2, t2_b=t2, t3=t3, flags=flags, g6={})
    verdict = render_verdict(flags=flags, t2_a=t2, t2_b=t2)
    assert "AWAKENING_OBJECTIVE_TRADE_AUDIT" in audit
    assert TAG_OBJ_THIN in verdict
    assert HONESTY_PARAGRAPH in audit
    assert refuse_this_tape_hash("3930475515f9576a") == "3930475515f9576a"
    with pytest.raises(ObjProtocolError, match="refused old tape hash"):
        refuse_this_tape_hash("7923fa61deadbeef")
    with pytest.raises(ObjProtocolError, match="forbidden init"):
        assert_forbidden_init("baseline_a9ffa852_pi_star.zip", sha="a9ffa852dead")
    with pytest.raises(ObjProtocolError, match="forbidden init"):
        assert_forbidden_init(tmp_path / "awakening_conv_v1_pi_star.zip")
    assert "awakening_conv_flags.json" in origin_guard_paths()
    assert isinstance(snapshot_origin_artifacts(), dict)


def test_coverage_origin_guard_overwrite(tmp_path: Path) -> None:
    paths = origin_guard_paths(repo=tmp_path)
    target = paths["awakening_conv_flags.json"]
    target.parent.mkdir(parents=True)
    target.write_text("before\n", encoding="utf-8")
    before = snapshot_origin_artifacts(repo=tmp_path)
    assert before["awakening_conv_flags.json"]
    target.write_text("after\n", encoding="utf-8")
    with pytest.raises(ObjProtocolError, match="origin artifact overwritten"):
        assert_origin_untouched(before, repo=tmp_path)
    assert body_exam_enabled(True) is True
    assert body_exam_enabled(False) is False


def test_coverage_copy_baseline_and_trees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_run as run_mod
    from lumina_core.birth.awakening_obj_run import copy_baseline_zip, prepare_obj_trees

    art = tmp_path / "art"
    monkeypatch.setattr(run_mod, "ORIGIN_EYES_ZIP", tmp_path / "missing.zip")
    with pytest.raises(ObjProtocolError, match="frozen living MARK_EYES zip missing"):
        copy_baseline_zip(art)
    src = tmp_path / "eyes.zip"
    src.write_bytes(b"PK\x03\x04eyes")
    monkeypatch.setattr(run_mod, "ORIGIN_EYES_ZIP", src)
    monkeypatch.setattr(run_mod, "write_bytes_sha", lambda _p: "deadbeef" * 4)
    with pytest.raises(ObjProtocolError, match="baseline sha must be a9ffa852"):
        copy_baseline_zip(art)
    monkeypatch.setattr(run_mod, "write_bytes_sha", lambda _p: BASELINE_SHA256)
    assert copy_baseline_zip(art) == BASELINE_SHA256
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    monkeypatch.setattr(run_mod, "overlay_sim_config", lambda _p: None)
    reports, work, art2 = prepare_obj_trees(repo=tmp_path)
    assert reports.name == "awakening_obj_run"
    assert (work / "config.yaml").is_file()
    assert art2.is_dir()


def test_coverage_eval_guards_and_stats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_eval as eval_mod
    from lumina_core.birth.awakening_obj_eval import eval_obj_leg

    assert organism_stats([])["n_policy"] == 0
    assert policy_obs_dim(SimpleNamespace()) == -1
    assert policy_obs_dim(SimpleNamespace(observation_space=SimpleNamespace(shape=(46,)))) == 46
    zip_ok = tmp_path / BASELINE_ZIP_NAME
    zip_ok.write_bytes(b"PK")
    with pytest.raises(ObjProtocolError, match="seeds recorded"):
        eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base", leg="Z")
    with pytest.raises(ObjProtocolError, match="used_v2_child"):
        eval_obj_leg(
            holdout=[],
            work=tmp_path,
            art=tmp_path,
            zip_path=tmp_path / "awakening_mark_eyes_v2_pi_star.zip",
            kind="base",
            leg="A",
        )
    with pytest.raises(ObjProtocolError, match="refused PPO.load"):
        eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=tmp_path / "other.zip", kind="base", leg="A")
    monkeypatch.setattr(eval_mod, "TRAIN", True)
    with pytest.raises(ObjProtocolError, match="TRAIN must stay False"):
        eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base", leg="A")
    monkeypatch.setattr(eval_mod, "TRAIN", False)
    token = PATH_EXIT_K3_SHADOW.set(True)
    try:
        with pytest.raises(ObjProtocolError, match="hooks"):
            eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base", leg="A")
    finally:
        PATH_EXIT_K3_SHADOW.reset(token)
    monkeypatch.setattr(eval_mod, "load_frozen_policy", lambda _p: None)
    missing = eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base", leg="A")
    assert missing["S_MISSING"] is True
    assert missing["reason"] == "zip_unloadable"
    monkeypatch.setattr(
        eval_mod,
        "load_frozen_policy",
        lambda _p: SimpleNamespace(observation_space=SimpleNamespace(shape=(43,))),
    )
    dim = eval_obj_leg(holdout=[], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base", leg="A")
    assert dim["reason"] == "obs_dim 43!=46"
    monkeypatch.setattr(eval_mod, "load_split_cache", lambda *_a, **_k: None)
    assert run_obj_eval(work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base")["reason"] == "holdout_missing"
    with pytest.raises(ObjProtocolError, match="kind must be"):
        run_obj_eval(work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="other")
    monkeypatch.setattr(eval_mod, "TRAIN", True)
    with pytest.raises(ObjProtocolError, match="TRAIN flag False"):
        run_obj_eval(work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="base")


def test_coverage_eval_rollout_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_eval as eval_mod
    from lumina_core.birth.awakening_obj_eval import eval_obj_leg

    zip_ok = tmp_path / CHILD_ZIP_NAME
    zip_ok.write_bytes(b"PK")
    policy = SimpleNamespace(observation_space=SimpleNamespace(shape=(46,)))
    monkeypatch.setattr(eval_mod, "load_frozen_policy", lambda _p: policy)
    monkeypatch.setattr(eval_mod, "run_evaluate_only", lambda **_k: None)
    monkeypatch.setattr(eval_mod, "load_close_jsonl", lambda _p: [])
    stats = eval_obj_leg(holdout=[{"last": 1.0}], work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="child", leg="B")
    assert stats["S_MISSING"] is False
    assert stats["eval_force_open"] is False
    assert stats["obs_dim"] == 46
    monkeypatch.setattr(
        eval_mod,
        "load_split_cache",
        lambda *_a, **_k: SimpleNamespace(holdout=[{"last": 1.0}, {"last": 2.0}]),
    )
    monkeypatch.setattr(eval_mod, "split_holdout_ab", lambda rows: (rows[:1], rows[1:]))
    monkeypatch.setattr(eval_mod, "eval_obj_leg", lambda **_k: {**_book(), "S_MISSING": False})
    out = run_obj_eval(work=tmp_path, art=tmp_path, zip_path=zip_ok, kind="child")
    assert out["both_loaded"] is True
    assert out["eval_force_open"] is False
    assert out["learn_called"] is False


def test_coverage_train_guards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_train as train_mod

    with pytest.raises(ObjProtocolError, match="train seed"):
        pin_train_seed(1)
    pin_train_seed(20260913)
    with pytest.raises(ObjProtocolError, match="init_policy must be scratch"):
        run_obj_v1_train(work=tmp_path, art=tmp_path, init_zip=tmp_path / "fresh.zip")
    with pytest.raises(ObjProtocolError, match="timesteps"):
        run_obj_v1_train(work=tmp_path, art=tmp_path, timesteps=1)
    token = PATH_SHAPE_K3_SHADOW.set(True)
    try:
        with pytest.raises(ObjProtocolError, match="hooks"):
            run_obj_v1_train(work=tmp_path, art=tmp_path)
    finally:
        PATH_SHAPE_K3_SHADOW.reset(token)
    monkeypatch.setattr(train_mod, "load_obj_train_split", lambda _w: {"train": [], "holdout": [], "train_hash": ""})
    with pytest.raises(ObjProtocolError, match="TRAIN split empty"):
        run_obj_v1_train(work=tmp_path, art=tmp_path)
    with pytest.raises(ObjProtocolError, match="obj train split missing"):
        load_obj_train_split(tmp_path)


def test_coverage_train_mocked_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_train as train_mod

    art = tmp_path / "art"
    art.mkdir()
    monkeypatch.setattr(
        train_mod,
        "load_obj_train_split",
        lambda _w: {"train": [{"last": 1.0}], "holdout": [], "train_hash": "aa"},
    )

    class _Env:
        observation_space = SimpleNamespace(shape=(46,))

        def __init__(self, armed: bool) -> None:
            self.env = SimpleNamespace(envelope={"participation_envelope_enabled": armed})

    monkeypatch.setattr(train_mod, "make_mark_eyes_train_env", lambda *_a, **_k: _Env(False))
    with pytest.raises(ObjProtocolError, match="FORCE_OPEN train envelope"):
        run_obj_v1_train(work=tmp_path, art=art)
    monkeypatch.setattr(train_mod, "make_mark_eyes_train_env", lambda *_a, **_k: _Env(True))

    class _BadShape:
        observation_space = SimpleNamespace(shape=(43,))
        env = SimpleNamespace(envelope={"participation_envelope_enabled": True})

    monkeypatch.setattr(train_mod, "make_mark_eyes_train_env", lambda *_a, **_k: _BadShape())
    with pytest.raises(ObjProtocolError, match="observation space"):
        run_obj_v1_train(work=tmp_path, art=art)
    monkeypatch.setattr(train_mod, "make_mark_eyes_train_env", lambda *_a, **_k: _Env(True))

    class _Boom:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            raise RuntimeError("no sb3")

    missing = run_obj_v1_train(work=tmp_path, art=art, ppo_cls=_Boom)
    assert missing["status"] == "S_MISSING"
    assert missing["train_force_open"] is True

    class _Model:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            self.num_timesteps = 0
            self._n_updates = 0

        def set_random_seed(self, seed: int) -> None:
            _ = seed

        def learn(self, **_k: Any) -> None:
            raise RuntimeError("learn boom")

    class _Trainer:
        def __init__(self, engine: Any, model_dir: Path) -> None:
            _ = engine, model_dir

        def save_weights(self, path: str) -> None:
            Path(path).write_bytes(b"PK")

    monkeypatch.setattr(train_mod, "PPOTrainer", _Trainer)
    failed = run_obj_v1_train(work=tmp_path, art=art, ppo_cls=_Model)
    assert "learn()" in str(failed.get("error"))

    class _Zero:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            self.num_timesteps = 0
            self._n_updates = 0

        def set_random_seed(self, seed: int) -> None:
            _ = seed

        def learn(self, **_k: Any) -> None:
            return None

    zero = run_obj_v1_train(work=tmp_path, art=art, ppo_cls=_Zero)
    assert "actual_timesteps == 0" in str(zero.get("error"))

    class _Ok:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            self.num_timesteps = 10_000
            self._n_updates = 9

        def set_random_seed(self, seed: int) -> None:
            _ = seed

        def learn(self, **_k: Any) -> None:
            return None

    class _NoSave:
        def __init__(self, engine: Any, model_dir: Path) -> None:
            _ = engine, model_dir

        def save_weights(self, path: str) -> None:
            _ = path

    monkeypatch.setattr(train_mod, "PPOTrainer", _NoSave)
    nosave = run_obj_v1_train(work=tmp_path, art=art, ppo_cls=_Ok)
    assert "child zip missing" in str(nosave.get("error"))
    monkeypatch.setattr(train_mod, "PPOTrainer", _Trainer)
    monkeypatch.setattr(train_mod, "write_bytes_sha", lambda _p: BASELINE_SHA256)
    twin = run_obj_v1_train(work=tmp_path, art=art, ppo_cls=_Ok)
    assert "identical to a9ffa852" in str(twin.get("error"))
    monkeypatch.setattr(train_mod, "write_bytes_sha", lambda _p: "cf70ae5b" * 8)
    ok = run_obj_v1_train(
        work=tmp_path,
        art=art,
        ppo_cls=_Ok,
        learn_fn=lambda **_k: None,
    )
    assert ok["status"] == "ok"
    assert ok["actual_timesteps"] == 10_000
    assert ok["train_force_open"] is True
    assert ok["eval_force_open"] is False
    assert (art / CHILD_ZIP_NAME).is_file()


def test_coverage_persist_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_tape as tape

    ticks = [{"timestamp": "2025-11-04T00:00:00+00:00", "source": "synthetic_cloud_fixture", "last": 1.0}]
    monkeypatch.setattr(tape, "generate_obj_tape_ticks", lambda: (ticks, ["UP"], {"UP": 1, "DOWN": 1, "RANGE": 1}))
    monkeypatch.setattr(tape, "enrich_ticks_for_conv", lambda rows, **_k: [dict(x) for x in rows])
    split = SimpleNamespace(train=ticks, holdout=ticks, train_gen={"UP": 1}, hold_gen={"UP": 1})
    monkeypatch.setattr(tape, "split_per_phase_60_40", lambda *_a, **_k: split)
    monkeypatch.setattr(tape, "count_regimes_post_enrich", lambda _x: {"TREND_UP": 1})
    monkeypatch.setattr(tape, "trend_fracs", lambda _c: (0.29, 0.29))
    monkeypatch.setattr(tape, "compute_ticks_fingerprint", lambda _x: "rawhash")
    monkeypatch.setattr(tape, "actual_calendar_days_from_ticks", lambda _x: 90)
    monkeypatch.setattr(tape, "real_data_percentage", lambda _x: 0.0)
    monkeypatch.setattr(tape, "host_real_data_pct", lambda *_a, **_k: 0.0)
    monkeypatch.setattr(tape, "split_holdout_ab", lambda rows: (rows, rows))
    monkeypatch.setattr(
        tape,
        "save_birth_data_cache",
        lambda *_a, **_k: {
            "cache_manifest_path": "m",
            "ticks_cache_path": "t",
            "split_cache_path": "s",
        },
    )
    monkeypatch.setattr(tape, "write_fixture_sidecar", lambda *_a, **_k: None)
    monkeypatch.setattr(tape, "MIN_HOLDOUT_TICKS", 1)
    monkeypatch.setattr(tape, "MIN_TICKS_PER_LEG", 1)
    monkeypatch.setattr(tape, "world_ok_fracs", lambda **_k: False)
    work, art = tmp_path / "work", tmp_path / "art"
    work.mkdir()
    art.mkdir()
    with pytest.raises(ObjProtocolError, match="25/25"):
        tape.persist_obj_fixture(work, art)
    monkeypatch.setattr(tape, "real_data_percentage", lambda _x: 1.0)
    monkeypatch.setattr(tape, "world_ok_fracs", lambda **_k: True)
    with pytest.raises(ObjProtocolError, match="real_data_percentage"):
        tape.persist_obj_fixture(work, art)
    monkeypatch.setattr(tape, "real_data_percentage", lambda _x: 0.0)
    monkeypatch.setattr(tape, "MIN_HOLDOUT_TICKS", 80_000)
    with pytest.raises(ObjProtocolError, match="holdout"):
        tape.persist_obj_fixture(work, art)
    monkeypatch.setattr(tape, "MIN_HOLDOUT_TICKS", 1)
    monkeypatch.setattr(tape, "MIN_TICKS_PER_LEG", 40_000)
    with pytest.raises(ObjProtocolError, match="chronological half"):
        tape.persist_obj_fixture(work, art)
    monkeypatch.setattr(tape, "MIN_TICKS_PER_LEG", 1)
    out = tape.persist_obj_fixture(work, art)
    assert out["world_ok"] is True
    assert out["fixture_seed"] == OBJ_SEED


def test_coverage_generate_tape_thin_and_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_tape as tape

    et = ZoneInfo("America/New_York")
    start = datetime(2025, 11, 3, 18, 0, tzinfo=et)
    monkeypatch.setattr(tape, "_iter_session_times", lambda **_k: [start + timedelta(minutes=i) for i in range(10)])
    with pytest.raises(ObjProtocolError, match="too thin"):
        tape.generate_obj_tape_ticks()
    stamps = [start + timedelta(minutes=i) for i in range(1_200)]
    monkeypatch.setattr(tape, "_iter_session_times", lambda **_k: stamps)
    ticks, labels, counts = tape.generate_obj_tape_ticks()
    assert len(ticks) == 1_200
    assert "regime" not in ticks[0]
    assert counts["UP"] + counts["DOWN"] + counts["RANGE"] == 1_200
    assert len(labels) == 1_200


def test_coverage_run_mocked_exam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_obj_run as run_mod
    from lumina_core.birth.awakening_obj_run import _restore_exam_env, main, run_awakening_obj

    pinned_cfg = os.environ.get("LUMINA_CONFIG")
    _restore_exam_env({"LUMINA_CONFIG": None})
    assert "LUMINA_CONFIG" not in os.environ
    _restore_exam_env({"LUMINA_CONFIG": pinned_cfg or "config.yaml"})
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    birth = tmp_path / "reports" / "birth_cloud_run"
    birth.mkdir(parents=True)
    (birth / "LUMINA_BIRTH_EXPERIMENT_LOG.md").write_text("# birth\n", encoding="utf-8")
    obj_root = tmp_path / "reports" / "awakening_obj_run"
    monkeypatch.setattr(run_mod, "OBJ_ROOT", obj_root)
    monkeypatch.setattr(run_mod, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_mod, "overlay_sim_config", lambda _p: None)
    monkeypatch.setattr(run_mod, "copy_baseline_zip", lambda _art: BASELINE_SHA256)
    monkeypatch.setattr(run_mod, "snapshot_origin_artifacts", lambda **_k: {})
    monkeypatch.setattr(run_mod, "assert_origin_untouched", lambda *_a, **_k: None)
    monkeypatch.setattr(run_mod, "audit_real_door", lambda **_k: {"real_data_pct": 0.0, "G6_tag": "REAL_DOOR_LOCKED"})

    monkeypatch.setattr(run_mod, "persist_obj_fixture", lambda *_a, **_k: (_ for _ in ()).throw(ObjProtocolError("G1 fail")))
    missing = run_awakening_obj(repo=tmp_path)
    assert missing["tag"] == TAG_S_MISSING
    assert os.environ.get("LUMINA_CONFIG") == pinned_cfg

    monkeypatch.setattr(run_mod, "persist_obj_fixture", lambda *_a, **_k: _fixture())
    monkeypatch.setattr(run_mod, "run_obj_eval", lambda **_k: {"S_MISSING": True, "reason": "zip_unloadable", "both_loaded": False})
    g2 = run_awakening_obj(repo=tmp_path)
    assert g2["tag"] == TAG_S_MISSING

    monkeypatch.setattr(run_mod, "run_obj_eval", lambda **k: _eval_ok() if k.get("kind") == "base" else {"S_MISSING": True})
    monkeypatch.setattr(run_mod, "run_obj_v1_train", lambda **_k: {"status": "S_MISSING", "error": "no learn"})
    g3 = run_awakening_obj(repo=tmp_path)
    assert g3["tag"] == TAG_S_MISSING

    monkeypatch.setattr(
        run_mod,
        "run_obj_v1_train",
        lambda **_k: {
            "status": "ok",
            "child_sha256": "cf70ae5b" * 8,
            "learn_called": True,
            "actual_timesteps": 10_000,
            "train_force_open": True,
        },
    )
    monkeypatch.setattr(
        run_mod,
        "run_obj_eval",
        lambda **k: _eval_ok() if k.get("kind") == "base" else {**_eval_ok(), "S_MISSING": True, "reason": "G4"},
    )
    g4 = run_awakening_obj(repo=tmp_path)
    assert g4["tag"] == TAG_S_MISSING

    monkeypatch.setattr(run_mod, "run_obj_eval", lambda **_k: _eval_ok())
    thin = run_awakening_obj(repo=tmp_path)
    assert thin["tag"] == TAG_OBJ_THIN
    assert thin["eval_force_open"] is False
    assert thin["floor_waived"] is False
    assert thin["GENESIS_EYES_OK"] is False
    assert (obj_root / "AWAKENING_OBJ_VERDICT.md").is_file()
    assert "OBJECTIVE_TRADE" in (obj_root / "LUMINA_OBJ_EXPERIMENT_LOG.md").read_text(encoding="utf-8")
    assert POINTER.split("\n")[2] in (birth / "LUMINA_BIRTH_EXPERIMENT_LOG.md").read_text(encoding="utf-8")

    monkeypatch.setattr(run_mod, "audit_real_door", lambda **_k: {"real_data_pct": 100.0})
    g6 = run_awakening_obj(repo=tmp_path)
    assert g6["tag"] == TAG_S_MISSING

    monkeypatch.setattr(run_mod, "persist_obj_fixture", lambda *_a, **_k: _fixture(real_data_pct=100.0))
    monkeypatch.setattr(run_mod, "audit_real_door", lambda **_k: {"real_data_pct": 0.0})
    pct = run_awakening_obj(repo=tmp_path)
    assert pct["tag"] == TAG_S_MISSING

    monkeypatch.setattr(run_mod, "run_awakening_obj", lambda **_k: {"tag": TAG_OBJ_THIN})
    assert main() == 0
    assert os.environ.get("LUMINA_CONFIG") == pinned_cfg


def test_coverage_force_open_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_mark_eyes_env as env_mod
    from lumina_core.birth.awakening_mark_eyes_env import _apply_train_force_open, make_mark_eyes_train_env

    inner = SimpleNamespace(envelope={})
    _apply_train_force_open(inner, force_open=False)
    assert inner.envelope["participation_envelope_enabled"] is False
    _apply_train_force_open(inner, force_open=True)
    assert inner.envelope["participation_envelope_enabled"] is True

    class _Inner:
        action_space = SimpleNamespace()
        envelope: dict[str, Any] = {}
        _position = 0

        def reset(self, **_k: Any) -> Any:
            return None

    monkeypatch.setattr(env_mod, "make_select_train_env", lambda *_a, **_k: _Inner())
    env = make_mark_eyes_train_env([], workspace_root=".", reports_dir=".", max_steps=1, force_open=True)
    assert env.env.envelope["participation_envelope_enabled"] is True
    with pytest.raises(env_mod.MarkEyesProtocolError, match="tax_r"):
        make_mark_eyes_train_env([], workspace_root=".", reports_dir=".", max_steps=1, tax_r=0.1)
