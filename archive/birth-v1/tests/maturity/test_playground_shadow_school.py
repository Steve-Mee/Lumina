"""Shadow proof cannot write the tape. Green days ignore a JSON stamp and a refill."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_core.maturity.continuum import save_continuum, load_continuum
from lumina_core.maturity.playground.journal import experiment_path
from lumina_core.maturity.playground.school_days import green_day_streak, note_sim_refill
from lumina_core.maturity.playground.shadow_promote import promote_if_proven
from lumina_core.maturity.playground.tape import append_tape_row, tape_path


def _resolved(name: str, n: int, r: float) -> list[dict[str, float | str]]:
    return [{"name": name, "r": r, "win": r > 0} for _ in range(n)]


def _sense(root: Path, rows: list[dict[str, float | str]]) -> None:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_playground_sense.json").write_text(
        json.dumps({"resolved": rows, "signs": {"m5": 1, "m60": 1, "m240": 1}}),
        encoding="utf-8",
    )


@pytest.mark.unit
def test_shadow_row_cannot_enter_the_tape(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        append_tape_row(tmp_path, {"kind": "close", "shadow": "1", "r": 1.0, "policy": True})
    assert not tape_path(tmp_path).exists()


@pytest.mark.unit
def test_h1_promotion_is_retired(tmp_path: Path) -> None:
    rows = _resolved("h1", 150, 0.2) + _resolved("null_b", 150, -0.1)
    _sense(tmp_path, rows)
    promoted = promote_if_proven(tmp_path)
    assert promoted["ok"] is False
    assert promoted["reason"] == "search_retired"
    assert promoted["pass_now"] is False
    assert not tape_path(tmp_path).exists()
    assert not (tmp_path / "state" / "lumina_playground_living_policy.json").exists()


@pytest.mark.unit
def test_proving_ground_freezes_promotion(tmp_path: Path) -> None:
    data = load_continuum(tmp_path)
    data["active_phase"] = "proving_ground"
    save_continuum(tmp_path, data)
    _sense(tmp_path, _resolved("h1", 150, 0.4) + _resolved("null_b", 150, -0.2))
    verdict = promote_if_proven(tmp_path)
    assert verdict["reason"] == "search_retired"
    assert not (tmp_path / "state" / "lumina_playground_living_policy.json").exists()


@pytest.mark.unit
def test_refill_is_not_a_green_day(tmp_path: Path) -> None:
    note_sim_refill(tmp_path, cash_before=1000.0, cash_after=50000.0)
    text = experiment_path(tmp_path).read_text(encoding="utf-8")
    assert "not a session day" in text
    assert green_day_streak(tmp_path) == 0


@pytest.mark.unit
def test_promotion_restarts_the_green_streak(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.fills import record_policy_close

    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_playground_living_policy.json").write_text(
        json.dumps({"method": "h1", "since": "2026-10-02T00:00:00+00:00", "pass_now": False}),
        encoding="utf-8",
    )
    old = datetime(2026, 9, 14, 15, 0, tzinfo=timezone.utc)
    record_policy_close(
        tmp_path,
        order_id="OLD",
        entry_px=5000.0,
        exit_px=5010.0,
        stop_px=4990.0,
        target_px=5030.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        ts=old.isoformat(),
    )
    assert green_day_streak(tmp_path) == 0
    from lumina_core.maturity.playground.learning_book import append_name

    fresh = datetime(2026, 10, 2, 15, 0, tzinfo=timezone.utc)
    append_name(
        tmp_path,
        {
            "name": "school",
            "status": "hand",
            "hand_since_ns": int(datetime(2026, 10, 2, tzinfo=timezone.utc).timestamp() * 1_000_000_000),
            "freeze_stamp": "2026-10-02T00:00:00+00:00",
            "forward_bar": 30,
            "sentence": {"side": 1, "stop_pct": 0.002, "target_pct": 0.004, "hold": 30},
        },
    )
    from lumina_core.market.nt_fees import net_close_usd

    preview = {
        "instrument": "MES",
        "qty": 1,
        "entry_px": 5000.0,
        "exit_px": 5010.0,
        "side": 1,
    }
    net = float(net_close_usd(preview) or 0.0)
    record_policy_close(
        tmp_path,
        order_id="NEW",
        entry_px=5000.0,
        exit_px=5010.0,
        stop_px=4990.0,
        target_px=5030.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        ts=(fresh + timedelta(hours=1)).isoformat(),
        rule_name="school",
        session_open_equity=1000.0,
        session_close_equity=1000.0 + net,
    )
    assert green_day_streak(tmp_path) == 1


@pytest.mark.unit
def test_a_win_smaller_than_the_fee_is_not_green(tmp_path: Path) -> None:
    from lumina_core.maturity.playground.fills import record_policy_close

    record_policy_close(
        tmp_path,
        order_id="THIN",
        entry_px=5000.0,
        exit_px=5000.25,
        stop_px=4990.0,
        target_px=5010.0,
        side=1,
        qty=1,
        instrument="MES",
        mode="sim",
        source="orderpath",
        ts="2026-10-02T15:00:00+00:00",
    )
    assert green_day_streak(tmp_path) == 0
