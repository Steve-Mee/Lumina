"""ADR-0050 Playground law — n_P≥150 hard, JSON is not a fill, no Birth-tape pass."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.phase_specs import evaluate_exit_proofs
from lumina_core.maturity.playground.fills import (
    first_honest_fill,
    record_orderpath_fill,
    record_policy_close,
)
from lumina_core.maturity.playground.heal import heal_playground_from_law
from lumina_core.maturity.playground.law import (
    N_D_SCHOOL,
    PlaygroundSnapshot,
    evaluate_playground_exit,
    evaluate_playground_pass,
)
from lumina_core.market.nt_fees import net_close_usd
from lumina_core.maturity.playground.progress import save_playground_progress


def _pass_snap(**overrides: object) -> PlaygroundSnapshot:
    base: dict[str, object] = {
        "n_p": 160,
        "n_plant": 0,
        "occupancy": 0.40,
        "skill_wr": 0.50,
        "breakeven_wr": 0.42,
        "mean_r": 0.05,
        "median_loss_r": 1.2,
        "freeze_ok": True,
        "policy_only": True,
        "child_sha": "aa" * 32,
        "awakening_child_sha": "aa" * 32,
        "birth_sha": "bb" * 32,
        "baseline_zip_sha": "aa" * 32,
        "envelope_sealed": True,
        "envelope_breached": False,
        "deck_live": True,
        "mode": "sim",
        "first_fill": True,
        "first_fill_source": "orderpath",
        "green_days": 5,
    }
    base.update(overrides)
    return PlaygroundSnapshot(**base)  # type: ignore[arg-type]


def _seal(root: Path) -> str:
    import hashlib

    from lumina_core.birth.birth_exit_policy_export import resolve_pi_star_path
    from lumina_core.maturity.phase_runners.awakening_shot import (
        CHILD_META_NAME,
        INCUMBENT_LEDGER_NAME,
        INCUMBENT_PARENT_LEDGER_NAME,
        artifacts_dir,
        live_child_zip,
    )

    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_sim_envelope_sealed.json").write_text(
        json.dumps(
            {
                "sealed": True,
                "source": "test",
                "daily_loss_cap": -1000.0,
                "max_total_open_risk": 3000.0,
            }
        ),
        encoding="utf-8",
    )
    body = b"baseline-zip-v1"
    sha = hashlib.sha256(body).hexdigest()
    for path in (live_child_zip(root), resolve_pi_star_path(root)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    live_child_zip(root).with_name(CHILD_META_NAME).write_text(
        json.dumps({"sha256": sha}),
        encoding="utf-8",
    )
    art = artifacts_dir(root)
    art.mkdir(parents=True, exist_ok=True)
    row = '{"plant": false, "trade_r": -0.2, "ts_iso": "2026-07-22T12:00:00+00:00"}\n'
    child_ledger = art / INCUMBENT_LEDGER_NAME
    parent_ledger = art / INCUMBENT_PARENT_LEDGER_NAME
    child_ledger.write_text(row, encoding="utf-8")
    parent_ledger.write_text(row, encoding="utf-8")
    (state / "lumina_first_watch_baseline.json").write_text(
        json.dumps(
            {
                "schema": "first_watch_baseline_v1",
                "zip_sha256": sha,
                "weight_sha256": "cc" * 32,
                "init_weight_sha256": "cc" * 32,
                "ledger_sha256": hashlib.sha256(child_ledger.read_bytes()).hexdigest(),
                "parent_ledger_sha256": hashlib.sha256(parent_ledger.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    return sha


def _write_pass_workspace(root: Path, *, n_p: int = 160) -> None:
    sha = _seal(root)
    (root / "state" / "lumina_playground_risk_telemetry.json").write_text(
        json.dumps(
            {
                "daily_pnl": 0.0,
                "realized_pnl_today": 0.0,
                "open_risk": 0.0,
                "mode": "sim",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    save_playground_progress(
        root,
        {
            "occupancy": 0.40,
            "breakeven_wr": 0.42,
            "freeze_ok": True,
            "child_sha": sha,
            "awakening_child_sha": sha,
            "birth_sha": "bb" * 32,
            "deck_live": True,
            "mode": "sim",
            "envelope_breached": False,
        },
    )
    for i in range(n_p):
        # R is the venue move over the stop that went with the order.
        win = i % 2 == 0
        record_policy_close(
            root,
            order_id=f"SIM-{i}",
            entry_px=5000.0,
            exit_px=5020.0 if win else 4990.0,
            stop_px=4900.0,
            target_px=5300.0,
            side=1,
            qty=1,
            instrument="MES",
            mode="sim",
            source="orderpath",
        )


def _install_hand(root: Path) -> None:
    from lumina_core.maturity.playground.learning_book import append_name

    append_name(
        root,
        {
            "name": "school",
            "status": "hand",
            "hand_since_ns": int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1_000_000_000),
            "freeze_stamp": "2026-09-01T00:00:00+00:00",
            "forward_bar": 30,
            "sentence": {"side": 1, "stop_pct": 0.002, "target_pct": 0.004, "hold": 30},
        },
    )


def _write_five_green_days(root: Path) -> None:
    sha = _seal(root)
    (root / "state" / "lumina_playground_risk_telemetry.json").write_text(
        json.dumps({"daily_pnl": 0.0, "open_risk": 0.0, "mode": "sim", "ts": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    save_playground_progress(
        root,
        {
            "occupancy": 0.40,
            "freeze_ok": True,
            "child_sha": sha,
            "awakening_child_sha": sha,
            "birth_sha": "bb" * 32,
            "deck_live": True,
            "mode": "sim",
            "envelope_breached": False,
        },
    )
    _install_hand(root)
    day = date(2026, 9, 14)
    written = 0
    while written < 5:
        if day.weekday() < 5:
            stamp = datetime(day.year, day.month, day.day, 15, 0, tzinfo=timezone.utc).isoformat()
            preview = {
                "instrument": "MES",
                "qty": 1,
                "entry_px": 5000.0,
                "exit_px": 5010.0,
                "side": 1,
            }
            net = float(net_close_usd(preview) or 0.0)
            record_policy_close(
                root,
                order_id=f"SIM-D{written}",
                entry_px=5000.0,
                exit_px=5010.0,
                stop_px=4990.0,
                target_px=5030.0,
                side=1,
                qty=1,
                instrument="MES",
                mode="sim",
                source="orderpath",
                ts=stamp,
                rule_name="school",
                session_open_equity=1000.0,
                session_close_equity=1000.0 + net,
            )
            written += 1
        day += timedelta(days=1)


@pytest.mark.unit
def test_four_green_days_cannot_pass() -> None:
    result = evaluate_playground_pass(_pass_snap(green_days=N_D_SCHOOL - 1, n_p=0))
    assert result.passed is False
    assert result.clock_open is True
    assert any(f"green_days={N_D_SCHOOL - 1}" in b for b in result.blockers)


@pytest.mark.unit
def test_full_and_passes() -> None:
    result = evaluate_playground_pass(_pass_snap(n_p=0, mean_r=-0.2, skill_wr=0.2))
    assert result.passed is True
    assert "green_days>=5" in result.proofs
    assert "economic_viability" not in result.proofs


@pytest.mark.unit
def test_birth_fitness_wr_is_not_the_school_gate() -> None:
    result = evaluate_playground_pass(
        _pass_snap(skill_wr=0.30, breakeven_wr=0.42, mean_r=-0.20, green_days=5)
    )
    assert result.passed is True


@pytest.mark.unit
def test_missing_be_is_not_the_school_gate() -> None:
    result = evaluate_playground_pass(_pass_snap(breakeven_wr=None, green_days=5))
    assert result.passed is True


@pytest.mark.unit
def test_json_stamp_is_not_a_green_day(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "lumina_playground_progress.json").write_text(
        json.dumps({"green_days": 5, "pass_now": True}),
        encoding="utf-8",
    )
    ok, missing, _learned = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert any("green_days=" in item for item in missing)


@pytest.mark.unit
def test_soft_complete_cannot_set_ok() -> None:
    result = evaluate_playground_pass(_pass_snap(n_p=1, first_fill=False, green_days=1))
    assert result.passed is False


@pytest.mark.unit
def test_a_changed_ledger_breaks_the_seal(tmp_path: Path) -> None:
    from lumina_core.maturity.awakening.baseline import seal_matches_disk
    from lumina_core.maturity.phase_runners.awakening_shot import (
        INCUMBENT_LEDGER_NAME,
        artifacts_dir,
    )

    _seal(tmp_path)
    assert seal_matches_disk(tmp_path)
    ledger = artifacts_dir(tmp_path) / INCUMBENT_LEDGER_NAME
    ledger.write_text('{"plant": false, "trade_r": 5.0, "ts_iso": "2026-07-22T12:00:00+00:00"}\n', encoding="utf-8")
    assert seal_matches_disk(tmp_path) == {}


def test_freeze_and_child_gates() -> None:
    frozen = evaluate_playground_pass(_pass_snap(freeze_ok=False))
    assert frozen.passed is False
    swapped = evaluate_playground_pass(_pass_snap(child_sha="cc" * 32))
    assert swapped.passed is False
    same_as_birth = evaluate_playground_pass(
        _pass_snap(child_sha="bb" * 32, awakening_child_sha="bb" * 32, baseline_zip_sha="")
    )
    assert same_as_birth.passed is False
    sealed_plant = evaluate_playground_pass(
        _pass_snap(
            child_sha="bb" * 32,
            awakening_child_sha="bb" * 32,
            birth_sha="bb" * 32,
            baseline_zip_sha="bb" * 32,
        )
    )
    assert sealed_plant.passed is True


@pytest.mark.unit
def test_real_mode_fails() -> None:
    result = evaluate_playground_pass(_pass_snap(mode="real"))
    assert result.passed is False
    assert any("mode_not_sim" in b for b in result.blockers)


@pytest.mark.unit
def test_occupancy_is_not_the_school_gate() -> None:
    occ = evaluate_playground_pass(_pass_snap(occupancy=1.0, green_days=5))
    assert occ.passed is True
    proc = evaluate_playground_pass(_pass_snap(median_loss_r=2.0, green_days=4))
    assert proc.passed is False
    assert any("green_days=4" in b for b in proc.blockers)


@pytest.mark.unit
def test_json_stamp_file_is_not_honest_fill(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "first_sim_order.json").write_text(
        json.dumps({"placed": True, "order_id": "FAKE-1"}),
        encoding="utf-8",
    )
    assert first_honest_fill(tmp_path) is None
    ok, missing, _ = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert any("green_days=" in item for item in missing)


@pytest.mark.unit
def test_orderpath_fill_counts(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=5124.25,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
    )
    assert rec["ok"] is True
    fill = first_honest_fill(tmp_path)
    assert fill is not None
    assert fill["order_id"] == "SIM-1"


@pytest.mark.unit
def test_health_source_rejected(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=1.0,
        qty=1,
        instrument="MES",
        mode="sim",
        source="fabric_health",
    )
    assert rec["ok"] is False
    assert rec["reason"] == "source_not_orderpath"


@pytest.mark.unit
def test_workspace_without_five_green_days_stays_open(tmp_path: Path) -> None:
    _write_pass_workspace(tmp_path, n_p=160)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "playground")
    assert ok is False
    assert any("green_days=" in m for m in missing)
    assert learned.get("clock_open") is True
    assert learned.get("pass_now") is False


@pytest.mark.unit
def test_workspace_five_green_days_pass(tmp_path: Path) -> None:
    _write_five_green_days(tmp_path)
    ok, missing, learned = evaluate_exit_proofs(tmp_path, "playground")
    assert ok is True
    assert missing == []
    assert learned.get("pass_now") is True
    assert "green_days>=5" in (learned.get("exit_proofs") or [])


@pytest.mark.unit
def test_heal_reopens_false_stamp(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={"soft": True}, exit_proofs=["deck_unlocked"])
    result = heal_playground_from_law(tmp_path)
    assert result["healed"] is True
    data = load_continuum(tmp_path)
    assert "playground" not in (data.get("completed_phases") or [])
    assert "awakening" in (data.get("completed_phases") or [])
    assert "birth" in (data.get("completed_phases") or [])


@pytest.mark.unit
def test_empty_demo_cash_asks_for_50000(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.demo_cash import note_refill_needed_once, refill_needed
    from lumina_core.maturity.playground.envelope import write_operator_seal

    assert refill_needed(None) is False
    assert refill_needed(50_000.0) is False
    assert refill_needed(0.0) is True
    write_operator_seal(
        tmp_path,
        daily_loss_cap=-1000.0,
        max_total_open_risk=3000.0,
        source="test",
        cash=0.0,
        floor_basis="cash",
    )
    line = note_refill_needed_once(tmp_path)
    assert line is not None
    assert "50.000" in line or "50000" in line
    assert "geen groene dag" in line
    again = note_refill_needed_once(tmp_path)
    assert again == line


def test_a_deep_loss_does_not_stop_the_school(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.envelope import assess_envelope, write_operator_seal, write_risk_telemetry

    write_operator_seal(
        tmp_path,
        daily_loss_cap=-1000.0,
        max_total_open_risk=3000.0,
        source="test",
        cash=50_000.0,
    )
    write_risk_telemetry(
        tmp_path,
        realized_pnl_today=-8000.0,
        daily_pnl=-8000.0,
        open_risk=10.0,
        mode="sim",
    )
    reading = assess_envelope(tmp_path, n_p=1, bars_flowing=True)
    assert reading["loss_floor_hit"] is True
    assert reading["breached"] is False


def test_missing_envelope_file_is_unsealed(tmp_path: Path) -> None:
    ok, missing, learned = evaluate_playground_exit(tmp_path)
    assert ok is False
    assert "sim_envelope_sealed" in missing
    assert "skill_not_policy_only" not in missing
    assert learned.get("policy_only") is True


@pytest.mark.unit
def test_runner_does_not_stamp_deck_or_json_fill(tmp_path: Path) -> None:
    from lumina_core.maturity.maturation_progress import load_maturation_progress
    from lumina_core.maturity.phase_runners.playground import run_playground

    result = run_playground(tmp_path, should_stop=lambda: True, poll_sec=0.0, sleep_fn=lambda _s: None)
    assert result["ok"] is False
    reached = load_maturation_progress(tmp_path).milestones_reached
    assert "deck_unlocked" not in reached
    assert "first_sim_order_placed" not in reached
    from lumina_core.maturity.playground.progress import load_playground_progress

    assert load_playground_progress(tmp_path).get("deck_live") is not True
