"""19:24 midpoint D13: power rule, CLI control cycle, locked midpoints."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lumina_research.cycles.midpoint_d13 import (
    POWER_CLEAN,
    POWER_NULL_LEAK,
    POWER_PROBLEM,
    GeometryScore,
    magnitude_label,
    overall_verdict,
    power_verdict,
    run_midpoint_power_floor,
)
from lumina_research.cycles.positive_control import (
    FADE_MIDPOINT_ATR,
    PLANTED_POWER_FLOOR_MAGNITUDES,
    PLANTED_POWER_MAGNITUDES,
    horizon_note,
    required_midpoint_controls,
)
from lumina_research.proof.cli import build_parser, main as proof_main


def _score(*, name: str, detected: bool, n_edge: int, verdict: str) -> GeometryScore:
    return GeometryScore(
        name=name,
        target_atr=1.0,
        stop_atr=1.2,
        planted_detected=detected,
        planted_median_oos=1.0 if detected else -1.0,
        planted_pct_positive=0.75 if detected else 0.25,
        planted_dsr=0.99 if detected else 0.1,
        planted_passed_gate=detected,
        effect_clears_threshold=detected,
        planted_beats_null=detected,
        n_a2=n_edge,
        n_edge=n_edge,
        n_seeds=32,
        exact_a2=f"{n_edge}/32",
        exact_edge=f"{n_edge}/32",
        null_median_of_medians=0.0,
        null_reliable=n_edge <= 3,
        power_verdict=verdict,
        n_trials=33,
        n_days=40,
        accepted=detected and n_edge <= 3,
    )


@pytest.mark.unit
def test_power_verdict_silent_null_and_missed_plant_is_power_problem() -> None:
    assert power_verdict(planted_detected=True, n_edge=0, n_seeds=32) == POWER_CLEAN
    assert power_verdict(planted_detected=False, n_edge=0, n_seeds=32) == POWER_PROBLEM
    assert power_verdict(planted_detected=False, n_edge=3, n_seeds=32) == POWER_PROBLEM
    assert power_verdict(planted_detected=True, n_edge=4, n_seeds=32) == POWER_NULL_LEAK
    assert power_verdict(planted_detected=False, n_edge=4, n_seeds=32) == POWER_NULL_LEAK


@pytest.mark.unit
def test_overall_verdict_prefers_leak_then_power() -> None:
    clean = _score(name="fade", detected=True, n_edge=0, verdict=POWER_CLEAN)
    miss = _score(name="breakout", detected=False, n_edge=0, verdict=POWER_PROBLEM)
    leak = _score(name="breakout", detected=True, n_edge=4, verdict=POWER_NULL_LEAK)
    assert overall_verdict((clean, clean)) == POWER_CLEAN
    assert overall_verdict((clean, miss)) == POWER_PROBLEM
    assert overall_verdict((miss, leak)) == POWER_NULL_LEAK


@pytest.mark.unit
def test_midpoint_horizon_note_states_exact_multiples() -> None:
    fade_t, fade_s = FADE_MIDPOINT_ATR
    note = horizon_note("atr", target_atr=fade_t, stop_atr=fade_s)
    assert "1×ATR14 target / 1.2×ATR14 stop" in note
    assert "1.5×ATR14" not in note
    assert "1.5" in horizon_note("atr")


@pytest.mark.unit
def test_cli_midpoint_d13_is_a_control_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "midpoint-d13", "--es-csv", "local.csv"])
    assert args.cycle == "midpoint-d13"
    assert args.es_csv == Path("local.csv")

    class _Power:
        overall_verdict = POWER_PROBLEM

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_d13", lambda **_kwargs: _Power())
    assert proof_main(["research", "--cycle", "midpoint-d13", "--work-dir", str(tmp_path)]) == 2

    class _Clean:
        overall_verdict = POWER_CLEAN

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_d13", lambda **_kwargs: _Clean())
    assert proof_main(["research", "--cycle", "midpoint-d13", "--work-dir", str(tmp_path)]) == 0


@pytest.mark.unit
def test_cli_midpoint_power_is_a_control_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "midpoint-power", "--es-csv", "local.csv"])
    assert args.cycle == "midpoint-power"

    class _Dirty:
        full_magnitude_clean = False

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_power", lambda **_kwargs: _Dirty())
    assert proof_main(["research", "--cycle", "midpoint-power", "--work-dir", str(tmp_path)]) == 2

    class _Clean:
        full_magnitude_clean = True

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_power", lambda **_kwargs: _Clean())
    assert proof_main(["research", "--cycle", "midpoint-power", "--work-dir", str(tmp_path)]) == 0


@pytest.mark.unit
def test_cli_midpoint_power_floor_is_a_control_cycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parser = build_parser()
    args = parser.parse_args(["research", "--cycle", "midpoint-power-floor", "--es-csv", "local.csv"])
    assert args.cycle == "midpoint-power-floor"

    class _Leak:
        null_leaked = True

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_power_floor", lambda **_kwargs: _Leak())
    assert proof_main(["research", "--cycle", "midpoint-power-floor", "--work-dir", str(tmp_path)]) == 2

    class _Measured:
        null_leaked = False

    monkeypatch.setattr("lumina_research.proof.cli.run_midpoint_power_floor", lambda **_kwargs: _Measured())
    assert proof_main(["research", "--cycle", "midpoint-power-floor", "--work-dir", str(tmp_path)]) == 0


@pytest.mark.unit
def test_cli_midpoint_d13_requires_es_csv(tmp_path: Path) -> None:
    assert (
        proof_main(
            [
                "research",
                "--cycle",
                "midpoint-d13",
                "--work-dir",
                str(tmp_path),
                "--report-dir",
                str(tmp_path),
            ]
        )
        == 2
    )


@pytest.mark.unit
def test_required_midpoints_stay_locked() -> None:
    assert required_midpoint_controls() == (("fade", 1.0, 1.2), ("breakout", 1.8, 0.9))


@pytest.mark.unit
def test_power_magnitudes_stay_locked() -> None:
    assert PLANTED_POWER_MAGNITUDES == (1.0, 0.5, 0.25)
    assert PLANTED_POWER_FLOOR_MAGNITUDES == (0.125, 0.0625)
    assert magnitude_label(0.125) == "0p125"
    assert magnitude_label(0.0625) == "0p0625"


@pytest.mark.unit
def test_power_floor_rejects_unlocked_magnitudes(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="locked to 0.125, 0.0625"):
        run_midpoint_power_floor(
            work_dir=tmp_path,
            report_dir=tmp_path,
            es_csv=tmp_path / "es.csv",
            magnitudes=(0.1, 0.05),
        )


@pytest.mark.unit
def test_committed_midpoint_d13_json_is_clean() -> None:
    payload = json.loads(Path("experiments/reports/phase5_p2_midpoint_d13.json").read_text(encoding="utf-8"))
    assert payload["overall_verdict"] == POWER_CLEAN
    assert payload["templates_run"] is False
    assert payload["research_run"] is False
    assert payload["holdout_opened"] is False
    by_name = {row["name"]: row for row in payload["geometries"]}
    assert by_name["fade"]["planted_detected"] is True
    assert by_name["breakout"]["planted_detected"] is True
    assert by_name["fade"]["exact_edge"] == "0/32"
    assert by_name["breakout"]["exact_edge"] == "0/32"


@pytest.mark.unit
def test_committed_midpoint_power_json_is_clean_and_gate_passes() -> None:
    payload = json.loads(Path("experiments/reports/phase5_p2_midpoint_power.json").read_text(encoding="utf-8"))
    assert payload["full_magnitude_clean"] is True
    assert payload["templates_run"] is False
    assert payload["research_run"] is False
    assert payload["holdout_opened"] is False
    assert payload["nq_closed"] is True
    assert payload["magnitudes"] == [1.0, 0.5, 0.25]
    by_mag = {row["planted_magnitude"]: row for row in payload["bands"]}
    for magnitude in (1.0, 0.5, 0.25):
        band = by_mag[magnitude]
        assert band["overall_verdict"] == POWER_CLEAN
        names = {row["name"]: row for row in band["geometries"]}
        for name in ("fade", "breakout"):
            row = names[name]
            assert row["planted_detected"] is True
            assert row["planted_passed_gate"] is True
            assert row["planted_reject_reasons"] == []
            assert row["planted_pbo_n_configs"] == 33
            assert row["exact_edge"] == "0/32"
            assert row["n_trials"] == 33


@pytest.mark.unit
def test_limited_es_preregister_is_not_an_executed_run() -> None:
    text = Path("experiments/reports/phase5_p2_limited_es_preregister_2026-10-29.md").read_text(
        encoding="utf-8"
    )
    assert "**Not executed.**" in text
    assert "p2l-mr-es" in text
    assert "p2l-vx-es" in text
    assert "p2l-tod-es" in text
    assert "TOD decision: keep" in text
    assert "n configs stays 6" in text
    assert "NQ closed" in text
    assert "p2a-or-bo-es" in text
    assert "SIM / REAL" in text
    assert "Do not start this run" in text


@pytest.mark.unit
def test_committed_midpoint_power_floor_json_is_clean_and_gate_passes() -> None:
    payload = json.loads(
        Path("experiments/reports/phase5_p2_midpoint_power_floor.json").read_text(encoding="utf-8")
    )
    assert payload["null_leaked"] is False
    assert payload["templates_run"] is False
    assert payload["research_run"] is False
    assert payload["holdout_opened"] is False
    assert payload["nq_closed"] is True
    assert payload["magnitudes"] == [0.125, 0.0625]
    assert payload["csv_sha256"].startswith("6100588d")
    assert payload["n_bars_es"] == 818851
    assert payload["es_last_ts"] == "2026-01-28T22:00:00Z"
    by_mag = {row["planted_magnitude"]: row for row in payload["bands"]}
    for magnitude in (0.125, 0.0625):
        band = by_mag[magnitude]
        assert band["overall_verdict"] == POWER_CLEAN
        names = {row["name"]: row for row in band["geometries"]}
        for name in ("fade", "breakout"):
            row = names[name]
            assert row["planted_detected"] is True
            assert row["planted_passed_gate"] is True
            assert row["planted_reject_reasons"] == []
            assert row["planted_pbo_n_configs"] == 33
            assert row["n_trials"] == 33
            assert row["exact_edge"] == "0/32"
            assert row["exact_oos"] == "8/8"
            assert row["planted_n_oos_windows"] == 8
            assert row["planted_n_positive_oos"] == 8
            assert row["planted_dsr"] == 1.0


@pytest.mark.unit
def test_power_floor_preregister_locks_125_and_625_before_a_run() -> None:
    text = Path("experiments/reports/phase5_p2_midpoint_power_floor_preregister_2026-10-29.md").read_text(
        encoding="utf-8"
    )
    assert "0.125" in text
    assert "0.0625" in text
    assert "No strategy-run" in text
    assert "passed_gate" in text
    answers = Path("docs/research/ONDERZOEKERS-ANTWOORDEN-POWER-S4-20261029T2208.md")
    digest = hashlib.sha256(answers.read_bytes()).hexdigest()
    assert digest == "991138fdd4b741041e3288387dd8aaf89a09652329ada7eec7eaa0f037bfae9d"
