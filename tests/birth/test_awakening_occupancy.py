"""AWAKENING_OCCUPANCY_BALANCE: equal %3 blocks, 25/25, floor 150, both legs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.awakening_occupancy_eval import (
    _assert_eval_ready,
    organism_stats,
    policy_obs_dim,
    run_occupancy_eval,
)
from lumina_core.birth.awakening_occupancy_flags import (
    TAG_OCCUPANCY_BODY,
    TAG_OCCUPANCY_OK,
    TAG_OCCUPANCY_THIN,
    TAG_OCCUPANCY_WORLD_FAIL,
    TAG_S_HARM,
    TAG_S_MISSING,
    compose_occupancy_flags,
    compute_occupancy_leg,
    license_occupancy,
)
from lumina_core.birth.awakening_occupancy_report import render_audit, render_verdict
from lumina_core.birth import awakening_occupancy_run as occupancy_run
from lumina_core.birth.awakening_occupancy_run import (
    assert_origin_untouched,
    body_exam_enabled,
    copy_baseline_zip,
    origin_guard_paths,
    prepare_occupancy_trees,
    snapshot_origin_artifacts,
)
from lumina_core.birth.awakening_occupancy_tables import (
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_occupancy_tape import (
    ALLOWED_PHASE_BLOCKS,
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    MIN_TREND_DOWN_FRAC,
    MIN_TREND_UP_FRAC,
    OCCUPANCY_SEED,
    OccupancyProtocolError,
    assert_forbidden_init,
    assert_gen_counts_balanced,
    assert_phase_blocks,
    count_generator_labels,
    count_regimes_post_enrich,
    generate_occupancy_tape_ticks,
    generator_labels,
    inspect_occupancy_protocol,
    persist_occupancy_fixture,
    phase_index,
    refuse_this_tape_hash,
    trend_fracs,
    world_ok_fracs,
    write_bytes_sha,
)
from lumina_core.birth.awakening_occupancy_train import pin_train_seed, run_occupancy_v1_train
from lumina_core.birth.awakening_path_exit_k3 import PATH_EXIT_K3_SHADOW
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.rl.observation_builder import OBSERVATION_DIM

MODULES = (
    "lumina_core/birth/awakening_occupancy_tape.py",
    "lumina_core/birth/awakening_occupancy_flags.py",
    "lumina_core/birth/awakening_occupancy_eval.py",
    "lumina_core/birth/awakening_occupancy_train.py",
    "lumina_core/birth/awakening_occupancy_tables.py",
    "lumina_core/birth/awakening_occupancy_report.py",
    "lumina_core/birth/awakening_occupancy_run.py",
)


def _thick(*, n_h: int = 40, mean_r: float = 0.1, n_policy: int = 160, wr: float = 0.4) -> dict[str, object]:
    return {"n_policy": n_policy, "n_H": n_h, "mean_r": mean_r, "wr": wr, "n_W": 20, "bars_held_p50": 90.0}


def test_phase_wraps_mod_3() -> None:
    assert phase_index(0, 90, 6) == 0
    assert {(i * 6 // 90) % 3 for i in range(90)} == {0, 1, 2}
    for n in (90, 91, 92, 213120):
        seen = {phase_index(i, n, 6) for i in range(n)}
        assert seen == {0, 1, 2}
        for i in range(min(n, 40)):
            assert phase_index(i, n, 6) == (i * 6 // n) % 3
            assert phase_index(i, n, 12) == (i * 12 // n) % 3
    proto = inspect_occupancy_protocol()
    assert not str(proto["phase_formula_mod_3"]).endswith(":-1")


def test_blocks_only_6_or_12() -> None:
    assert ALLOWED_PHASE_BLOCKS == frozenset({6, 12})
    assert assert_phase_blocks(6) == 6
    assert assert_phase_blocks(12) == 12
    with pytest.raises(OccupancyProtocolError, match=r"PHASE_BLOCKS in \{6,12\}"):
        assert_phase_blocks(3)
    with pytest.raises(OccupancyProtocolError, match=r"PHASE_BLOCKS in \{6,12\}"):
        assert_phase_blocks(18)
    proto = inspect_occupancy_protocol()
    assert not str(proto["phase_blocks_6_or_12"]).endswith(":-1")


def test_gen_counts_balanced() -> None:
    for n, blocks in ((90, 6), (91, 6), (92, 6), (213120, 6), (213120, 12)):
        counts = count_generator_labels(generator_labels(n, blocks))
        assert_gen_counts_balanced(counts)
        vals = [counts["UP"], counts["DOWN"], counts["RANGE"]]
        assert max(vals) - min(vals) <= 2
        assert all(abs(v - n // 3) <= 2 for v in vals)
    proto = inspect_occupancy_protocol()
    assert not str(proto["gen_counts_n3"]).endswith(":-1")


def test_forbids_3_2_1() -> None:
    with pytest.raises(OccupancyProtocolError, match="3/2/1"):
        assert_gen_counts_balanced({"UP": 106560, "DOWN": 71040, "RANGE": 35520})
    with pytest.raises(OccupancyProtocolError, match="3/2/1"):
        assert_gen_counts_balanced({"UP": 3, "DOWN": 2, "RANGE": 1})


def test_exam_seed_20260910() -> None:
    assert OCCUPANCY_SEED == 20260910
    proto = inspect_occupancy_protocol()
    assert not str(proto["exam_seed_20260910"]).endswith(":-1")
    assert not str(proto["start_et_2026_02_02"]).endswith(":-1")
    assert not str(proto["drift_kappa_attempt2"]).endswith(":-1")


def test_body_not_called_without_world_ok() -> None:
    assert body_exam_enabled(False) is False
    assert body_exam_enabled(True) is True
    licensed = license_occupancy({}, {}, world_ok=False)
    assert licensed["tag"] == TAG_OCCUPANCY_WORLD_FAIL
    flags = compose_occupancy_flags(
        {
            "tag": TAG_OCCUPANCY_OK,
            "world_ok": False,
            "MOVED_A": True,
            "MOVED_B": True,
            "learn_called": True,
            "child_sha256": "deadbeef",
            "actual_timesteps": 10_000,
        }
    )
    assert flags["tag"] == TAG_OCCUPANCY_WORLD_FAIL
    assert flags["learn_called"] is False
    assert flags["child_sha256"] == ""
    proto = inspect_occupancy_protocol()
    assert not str(proto["body_skipped"]).endswith(":-1")


def test_floor_150() -> None:
    assert POLICY_EDGE_MIN_TRADES == 150
    src = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "POLICY_EDGE_MIN_TRADES = 150" in src
    proto = inspect_occupancy_protocol()
    assert "foundation_metrics.py:" in proto["floor_150"]
    assert not str(proto["floor_150"]).endswith(":-1")


def test_ok_requires_both_legs() -> None:
    base = _thick(n_h=40, mean_r=-0.20, n_policy=160)
    child = _thick(n_h=38, mean_r=-0.10, n_policy=160)
    a = compute_occupancy_leg(base, child)
    b = compute_occupancy_leg(base, child)
    licensed = license_occupancy(a, b, world_ok=True)
    assert licensed["tag"] == TAG_OCCUPANCY_OK
    assert licensed["law"] == "SHADOW"
    assert licensed["licensed_next_family"] == "AWAKENING_MARK_EYES"
    only_a = license_occupancy(
        a, compute_occupancy_leg(base, _thick(n_h=40, mean_r=-0.19, n_policy=160)), world_ok=True
    )
    assert only_a["tag"] == TAG_OCCUPANCY_BODY
    assert only_a["tag"] != TAG_OCCUPANCY_OK
    proto = inspect_occupancy_protocol()
    assert not str(proto["both_leg_license"]).endswith(":-1")
    flags = compose_occupancy_flags(
        {"GENESIS_EYES_OK": True, "tag": TAG_OCCUPANCY_OK, "MOVED_A": True, "MOVED_B": True, "world_ok": True}
    )
    assert flags["GENESIS_EYES_OK"] is False
    flags_a_only = compose_occupancy_flags(
        {"tag": TAG_OCCUPANCY_OK, "MOVED_A": True, "MOVED_B": False, "world_ok": True}
    )
    assert flags_a_only["tag"] == TAG_OCCUPANCY_BODY


def test_synthetic_pct_zero() -> None:
    assert real_data_percentage([{"source": "synthetic_cloud_fixture"}]) == 0.0
    proto = inspect_occupancy_protocol()
    assert not str(proto["honesty_synthetic_0"]).endswith(":-1")


def test_no_oracle_regime() -> None:
    banned = ("stamp_oracle_regime", "inject_oracle_regime", "write_regime_after_enrich")
    for rel in MODULES:
        text = Path(rel).read_text(encoding="utf-8")
        for name in banned:
            assert f"def {name}" not in text, f"{rel} defines {name}"
        assert 'tick["regime"] = gen' not in text
        assert "tick['regime'] = phase" not in text
        assert 'tick["regime"] = intended' not in text
        assert 'tick["regime"] = labels' not in text
    proto = inspect_occupancy_protocol()
    assert not str(proto["no_oracle_regime"]).endswith(":-1")


def test_modules_under_400() -> None:
    for rel in MODULES:
        n = sum(1 for _ in Path(rel).open(encoding="utf-8"))
        assert n <= 400, f"{rel} has {n} LOC"
    proto = inspect_occupancy_protocol()
    assert proto["gate0_complete"] is True
    assert OBSERVATION_DIM == 43
    assert MIN_TREND_UP_FRAC == 0.25
    assert MIN_TREND_DOWN_FRAC == 0.25
    assert PATH_EXIT_K3_SHADOW.get() is False
    assert PATH_SHAPE_K3_SHADOW.get() is False
    assert not str(proto["fracs_25_25"]).endswith(":-1")
    assert not str(proto["hooks_default_false"]).endswith(":-1")
    assert not str(proto["genesis_eyes_ok_forced_false"]).endswith(":-1")


def test_license_thin_harm_missing() -> None:
    base = _thick(n_h=40, mean_r=-0.10, n_policy=160)
    harm = compute_occupancy_leg(base, _thick(n_h=40, mean_r=-0.20, n_policy=160))
    assert harm["S_HARM"] is True
    licensed_h = license_occupancy(harm, harm, world_ok=True)
    assert licensed_h["tag"] == TAG_S_HARM
    thin = compute_occupancy_leg(base, _thick(n_h=40, mean_r=0.10, n_policy=20))
    assert thin["S_THIN"] is True
    licensed_t = license_occupancy(thin, thin, world_ok=True)
    assert licensed_t["tag"] == TAG_OCCUPANCY_THIN
    miss = compute_occupancy_leg({"n_policy": 160, "S_MISSING": True}, base, missing=True)
    licensed_m = license_occupancy(miss, miss, world_ok=True)
    assert licensed_m["tag"] == TAG_S_MISSING


def test_tables_and_report() -> None:
    t0 = table_t0_identity(origin_main="abc", train_hash="9b66", baseline_sha=BASELINE_SHA256, child_sha="")
    t1 = table_t1_honesty()
    t2 = table_t2_leg("A", compute_occupancy_leg(_thick(), _thick(mean_r=0.2)))
    t3 = table_t3_license({"tag": TAG_OCCUPANCY_BODY, "law": "NONE", "licensed_next_family": "H_NONE"})
    assert t0["fixture_seed"] == 20260910
    assert t1["pct_synthetic_cloud_fixture"] == 0.0
    assert t2["leg"] == "A"
    assert t3["GENESIS_EYES_OK"] is False
    flags = compose_occupancy_flags({"world_ok": False, "tag": TAG_OCCUPANCY_WORLD_FAIL})
    audit = render_audit(gate0={"ok": True}, proto={"gate0_complete": True}, t0=t0, t1=t1, t2_a=t2, t2_b=t2, t3=t3, flags=flags, g6={"G6_tag": "REAL_DOOR_LOCKED"})
    verdict = render_verdict(flags=flags, t2_a=t2, t2_b=t2)
    assert "OCCUPANCY_WORLD_FAIL" in audit
    assert "VERDICT is from disk" in verdict


def test_tape_helpers_and_generate() -> None:
    assert world_ok_fracs(train_up=0.25, train_down=0.25, hold_up=0.25, hold_down=0.25) is True
    assert world_ok_fracs(train_up=0.24, train_down=0.25, hold_up=0.25, hold_down=0.25) is False
    assert refuse_this_tape_hash("9b66a1625937d161") == "9b66a1625937d161"
    with pytest.raises(OccupancyProtocolError, match="old tape hash"):
        refuse_this_tape_hash("8d1aa6f8deadbeef")
    with pytest.raises(OccupancyProtocolError, match="forbidden init sha"):
        assert_forbidden_init("child.zip", sha=BASELINE_SHA256)
    with pytest.raises(OccupancyProtocolError, match="forbidden init"):
        assert_forbidden_init("genesis_mark_eyes_pi_star.zip")
    counts = count_regimes_post_enrich([{"regime": "TREND_UP"}, {}, {"regime": "TREND_DOWN"}])
    assert trend_fracs(counts)[0] == pytest.approx(1.0 / 3.0)
    raw, gen = generate_occupancy_tape_ticks(blocks=6)
    assert gen == {"UP": 71040, "DOWN": 71040, "RANGE": 71040}
    assert all("regime" not in row for row in raw)
    assert raw[0]["source"] == "synthetic_cloud_fixture"


def test_persist_world_fail_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.birth import awakening_occupancy_tape as tape

    train = [{"regime": "TREND_UP"}] * 34000 + [{"regime": "TREND_DOWN"}] * 25000 + [{"regime": "NEUTRAL"}] * 64330
    hold = [{"regime": "TREND_UP"}] * 14000 + [{"regime": "TREND_DOWN"}] * 24000 + [{"regime": "NEUTRAL"}] * 48460
    result = SimpleNamespace(
        ticks=train + hold,
        split=SimpleNamespace(train=train, holdout=hold),
        fixture_manifest={"hash": "9b66a1625937d161", "holdout_tick_count": 86460},
    )
    monkeypatch.setattr(tape, "generate_occupancy_tape_ticks", lambda blocks=6: ([{"last": 1.0}] * 10, {"UP": 4, "DOWN": 3, "RANGE": 3}))
    monkeypatch.setattr(tape, "persist_cloud_fixture", lambda work, spec=None, ticks=None: result)
    monkeypatch.setattr(tape, "real_data_percentage", lambda rows: 0.0)
    monkeypatch.setattr(tape, "host_real_data_pct", lambda rows, certified_cache=False: 0.0)
    monkeypatch.setattr(tape, "split_holdout_ab", lambda rows: (rows[:40000], rows[40000:]))
    art = tmp_path / "art"
    art.mkdir()
    payload = persist_occupancy_fixture(tmp_path, art)
    assert payload["world_ok"] is False
    assert payload["phase_blocks_used"] == 6
    assert (art / "01_occupancy_fixture_manifest.json").is_file()


def test_eval_refuses_v2_and_missing_holdout(tmp_path: Path) -> None:
    with pytest.raises(OccupancyProtocolError, match="used_v2_child"):
        _assert_eval_ready("A", tmp_path / "awakening_mark_eyes_v2_pi_star.zip", "base")
    with pytest.raises(OccupancyProtocolError, match="non-occupancy"):
        _assert_eval_ready("A", tmp_path / "other.zip", "base")
    with pytest.raises(OccupancyProtocolError, match="A/B"):
        _assert_eval_ready("C", tmp_path / BASELINE_ZIP_NAME, "base")
    stats = organism_stats([])
    assert stats["n_policy"] == 0
    assert policy_obs_dim(SimpleNamespace(observation_space=SimpleNamespace(shape=(46,)))) == 46
    assert policy_obs_dim(SimpleNamespace()) == -1
    missing = run_occupancy_eval(work=tmp_path, art=tmp_path, zip_path=tmp_path / BASELINE_ZIP_NAME, kind="base")
    assert missing["S_MISSING"] is True
    assert missing["reason"] == "holdout_missing"


def test_train_scratch_only(tmp_path: Path) -> None:
    pin_train_seed(20260910)
    with pytest.raises(OccupancyProtocolError, match="train seed"):
        pin_train_seed(1)
    with pytest.raises(OccupancyProtocolError, match="forbidden init|scratch"):
        run_occupancy_v1_train(work=tmp_path, art=tmp_path, init_zip=tmp_path / BASELINE_ZIP_NAME)
    with pytest.raises(OccupancyProtocolError, match="timesteps"):
        run_occupancy_v1_train(work=tmp_path, art=tmp_path, init_zip=None, timesteps=50)
    token = PATH_EXIT_K3_SHADOW.set(True)
    try:
        with pytest.raises(OccupancyProtocolError, match="hooks"):
            run_occupancy_v1_train(work=tmp_path, art=tmp_path, init_zip=None)
    finally:
        PATH_EXIT_K3_SHADOW.reset(token)


def test_run_world_fail_skips_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        occupancy_run,
        "persist_occupancy_fixture",
        lambda work, art: {
            "world_ok": False,
            "hash": "9b66a1625937d161",
            "real_data_pct": 0.0,
            "source": "synthetic_cloud_fixture",
            "gen_up": 71040,
            "gen_down": 71040,
            "gen_range": 71040,
            "train_up_frac": 0.209,
            "train_down_frac": 0.209,
            "hold_up_frac": 0.162,
            "hold_down_frac": 0.277,
            "phase_blocks_used": 6,
        },
    )
    monkeypatch.setattr(occupancy_run, "_append_logs", lambda *args, **kwargs: None)
    flags = occupancy_run.run_awakening_occupancy(repo=tmp_path)
    assert flags["tag"] == TAG_OCCUPANCY_WORLD_FAIL
    assert flags["learn_called"] is False
    assert flags["child_sha256"] == ""
    assert flags["GENESIS_EYES_OK"] is False
    dest = tmp_path / "reports" / "awakening_occupancy_run" / "artifacts" / BASELINE_ZIP_NAME
    assert dest.is_file()
    assert write_bytes_sha(dest) == BASELINE_SHA256


def test_origin_guard_and_trees(tmp_path: Path) -> None:
    from lumina_core.birth.birth_exit_policy_export import file_sha256

    (tmp_path / "config.yaml").write_text(Path("config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    paths = origin_guard_paths(repo=tmp_path)
    assert "awakening_coupling_flags.json" in paths
    before = snapshot_origin_artifacts(repo=tmp_path)
    assert_origin_untouched(before, repo=tmp_path)
    _reports, work, art = prepare_occupancy_trees(repo=tmp_path)
    assert (work / "config.yaml").is_file()
    digest = copy_baseline_zip(art)
    assert digest == BASELINE_SHA256
    victim = paths["awakening_coupling_flags.json"]
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_text("mutated\n", encoding="utf-8")
    snap = {"awakening_coupling_flags.json": file_sha256(victim)[::-1]}
    with pytest.raises(OccupancyProtocolError, match="origin artifact overwritten"):
        assert_origin_untouched(snap, repo=tmp_path)
