"""Birth runtime diagnostics fingerprint contract."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.runtime_diagnostics import (
    BIRTH_DIAG_CONTRACT,
    collect_birth_code_fingerprint,
    fingerprint_identity_defects,
    identity_progress_fields_for_boot,
    log_birth_code_fingerprint,
    log_geometry_trace,
    log_meta_decision_trace,
    log_progress_write_trace,
    progress_diagnostic_fields,
    reset_runtime_diagnostics_for_tests,
)
from lumina_core.birth.stage_scorecard import SCORECARD_PRESERVE_KEYS

# Stable capture: Lumina loggers may not propagate to root, so caplog is unreliable
# under single-process coverage runs. Assert via monkeypatched logger methods.


@pytest.fixture(autouse=True)
def _reset_runtime_diag() -> Iterator[None]:
    reset_runtime_diagnostics_for_tests()
    yield
    reset_runtime_diagnostics_for_tests()


@pytest.fixture
def diag_logs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """Capture runtime_diagnostics logger.info/warning messages."""
    captured: list[tuple[int, str]] = []

    def _format(msg: object, args: tuple[object, ...]) -> str:
        text = str(msg)
        if args:
            try:
                return text % args
            except Exception:
                return f"{text} {args!r}"
        return text

    def _info(msg: object, *args: object, **_kwargs: object) -> None:
        captured.append((logging.INFO, _format(msg, args)))

    def _warning(msg: object, *args: object, **_kwargs: object) -> None:
        captured.append((logging.WARNING, _format(msg, args)))

    monkeypatch.setattr(
        "lumina_core.birth.runtime_diagnostics.logger.info",
        _info,
    )
    monkeypatch.setattr(
        "lumina_core.birth.runtime_diagnostics.logger.warning",
        _warning,
    )
    return captured


def _records(captured: list[tuple[int, str]], needle: str) -> list[tuple[int, str]]:
    return [(level, msg) for level, msg in captured if needle in msg]


@pytest.mark.unit
def test_fingerprint_has_contract_and_features() -> None:
    fp = collect_birth_code_fingerprint()
    assert fp["birth_diag_contract"] == BIRTH_DIAG_CONTRACT
    assert fp["birth_code_fingerprint"]
    assert fp["pid"] > 0
    assert "features" in fp
    assert fp["features"].get("periodic_has_failclosed") is True
    assert fp["features"].get("enrich_emits_birth_trade_stop") is True
    assert fp["features"].get("coerce_meta_plan") is True
    assert fingerprint_identity_defects(fp) == []


@pytest.mark.unit
def test_progress_diagnostic_fields_compact() -> None:
    fields = progress_diagnostic_fields()
    for k in (
        "birth_diag_contract",
        "birth_code_fingerprint",
        "birth_runtime_pid",
        "birth_code_has_quality_failclosed",
        "birth_code_has_geom_enrich",
        "birth_code_has_coerce",
        "birth_code_identity_ok",
        "birth_code_identity_defects",
    ):
        assert k in fields
    assert fields["birth_diag_contract"] == BIRTH_DIAG_CONTRACT
    assert fields["birth_code_identity_ok"] is True
    assert fields["birth_code_identity_defects"] == []


@pytest.mark.unit
def test_identity_keys_are_preserved_on_progress() -> None:
    assert "birth_code_identity_ok" in SCORECARD_PRESERVE_KEYS
    assert "birth_code_identity_defects" in SCORECARD_PRESERVE_KEYS
    assert "birth_code_fingerprint" in SCORECARD_PRESERVE_KEYS


@pytest.mark.unit
def test_healthy_fingerprint_logs_info_once_without_module_dump(
    diag_logs: list[tuple[int, str]],
) -> None:
    log_birth_code_fingerprint(reason="boot")
    log_birth_code_fingerprint(reason="attach")
    lines = _records(diag_logs, "birth.runtime.fingerprint")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO
    assert "reason=boot" in lines[0][1]
    assert "defects=none" in lines[0][1]
    assert _records(diag_logs, "birth.runtime.module") == []


@pytest.mark.unit
def test_defective_fingerprint_warns_every_call_with_module_dump(
    diag_logs: list[tuple[int, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake: dict[str, Any] = {
        "birth_diag_contract": BIRTH_DIAG_CONTRACT,
        "birth_code_fingerprint": "deadbeefdeadbeef",
        "pid": 1,
        "python_executable": "x",
        "cwd": "y",
        "sys_path_repo_hit": False,
        "features": {},
        "modules": {
            "lumina_core.birth.missing_mod": {
                "path": None,
                "mtime": "import_failed",
                "sha12": "na",
            }
        },
    }
    monkeypatch.setattr(
        "lumina_core.birth.runtime_diagnostics.collect_birth_code_fingerprint",
        lambda: fake,
    )
    log_birth_code_fingerprint(reason="bad1")
    log_birth_code_fingerprint(reason="bad2")
    lines = _records(diag_logs, "birth.runtime.fingerprint")
    assert len(lines) == 2
    assert all(level == logging.WARNING for level, _ in lines)
    assert "repo_not_on_path" in lines[0][1]
    modules = _records(diag_logs, "birth.runtime.module")
    assert len(modules) == 2
    assert all(level == logging.WARNING for level, _ in modules)


@pytest.mark.unit
def test_fingerprint_identity_defects_detects_off_tree_and_probes() -> None:
    fp: dict[str, Any] = {
        "birth_diag_contract": "old_contract",
        "sys_path_repo_hit": True,
        "features": {
            "periodic_has_failclosed": True,
            "enrich_emits_birth_trade_stop": True,
            "coerce_meta_plan": True,
            "geometry_has_is_time_ordered": True,
            "geometry_rejects_disordered": True,
        },
        "modules": {
            "lumina_core.birth.runtime_diagnostics": {
                "path": "/tmp/other_repo/runtime_diagnostics.py",
                "mtime": "2026-08-14T00:00:00",
                "sha12": "abc123abc123",
            }
        },
    }
    defects = fingerprint_identity_defects(fp)
    assert "contract_mismatch" in defects
    assert "off_tree:runtime_diagnostics" in defects


@pytest.mark.unit
def test_progress_write_trace_healthy_info_once(diag_logs: list[tuple[int, str]]) -> None:
    scorecard = {
        "birth_code_fingerprint": "abc",
        "birth_code_identity_ok": True,
        "birth_code_identity_defects": [],
        "birth_trade_stop_pct": 0.0012,
        "birth_trade_geometry_source": "move_distribution",
        "geometry_time_ordered": True,
    }
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=10,
        scorecard=scorecard,
    )
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=20,
        scorecard=scorecard,
    )
    lines = _records(diag_logs, "birth.progress.write_trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO
    assert "defects=none" in lines[0][1]


@pytest.mark.unit
def test_progress_write_trace_unset_geometry_is_not_a_defect(
    diag_logs: list[tuple[int, str]],
) -> None:
    scorecard = {
        "birth_code_fingerprint": "abc",
        "birth_code_identity_ok": True,
        "birth_trade_stop_pct": 0.0,
        "birth_trade_geometry_source": "unset",
        "geometry_time_ordered": False,
        "geometry_macro_rejected": False,
    }
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=0,
        scorecard=scorecard,
    )
    lines = _records(diag_logs, "birth.progress.write_trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO
    assert "defects=none" in lines[0][1]


@pytest.mark.unit
def test_progress_write_trace_rejected_shuffle_is_not_a_defect(
    diag_logs: list[tuple[int, str]],
) -> None:
    scorecard = {
        "birth_code_fingerprint": "abc",
        "birth_code_identity_ok": True,
        "birth_trade_stop_pct": 0.0012,
        "birth_trade_geometry_source": "fallback",
        "geometry_time_ordered": False,
        "geometry_macro_rejected": True,
    }
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=10,
        scorecard=scorecard,
    )
    lines = _records(diag_logs, "birth.progress.write_trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO


@pytest.mark.unit
def test_progress_write_trace_disordered_unrejected_warns(
    diag_logs: list[tuple[int, str]],
) -> None:
    scorecard = {
        "birth_code_fingerprint": "abc",
        "birth_code_identity_ok": True,
        "birth_trade_stop_pct": 0.0012,
        "birth_trade_geometry_source": "fallback",
        "geometry_time_ordered": False,
        "geometry_macro_rejected": False,
    }
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=10,
        scorecard=scorecard,
        throttle_sec=0.0,
    )
    lines = _records(diag_logs, "birth.progress.write_trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.WARNING
    assert "geometry_not_time_ordered" in lines[0][1]


@pytest.mark.unit
def test_progress_write_trace_macro_geometry_warns(diag_logs: list[tuple[int, str]]) -> None:
    scorecard = {
        "birth_code_fingerprint": "abc",
        "birth_code_identity_ok": True,
        "birth_trade_stop_pct": 0.008,
        "birth_trade_geometry_source": "move_distribution",
        "geometry_time_ordered": True,
    }
    log_progress_write_trace(
        phase="curriculum_learning",
        curriculum_stage="stage2_range",
        stage_trades=10,
        scorecard=scorecard,
        throttle_sec=0.0,
    )
    lines = _records(diag_logs, "birth.progress.write_trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.WARNING
    assert "macro_move_distribution" in lines[0][1]


@pytest.mark.unit
def test_geometry_trace_healthy_is_info(diag_logs: list[tuple[int, str]]) -> None:
    log_geometry_trace(
        where="stage_prepare",
        stop_pct=0.0012,
        target_pct=0.0020,
        source="move_distribution",
        pool_size=400,
        time_ordered=True,
        macro_rejected=False,
    )
    lines = _records(diag_logs, "birth.geometry.trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO
    assert "defects=none" in lines[0][1]


@pytest.mark.unit
def test_geometry_trace_disordered_unrejected_warns(diag_logs: list[tuple[int, str]]) -> None:
    log_geometry_trace(
        where="stage_prepare",
        stop_pct=0.0012,
        target_pct=0.0020,
        source="fallback",
        pool_size=400,
        time_ordered=False,
        macro_rejected=False,
    )
    lines = _records(diag_logs, "birth.geometry.trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.WARNING
    assert "disordered_unrejected" in lines[0][1]


@pytest.mark.unit
def test_geometry_trace_rejected_shuffle_is_info(diag_logs: list[tuple[int, str]]) -> None:
    log_geometry_trace(
        where="stage_prepare",
        stop_pct=0.0012,
        target_pct=0.0020,
        source="fallback",
        pool_size=400,
        time_ordered=False,
        macro_rejected=True,
    )
    lines = _records(diag_logs, "birth.geometry.trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO


@pytest.mark.unit
def test_meta_decision_trace_is_info(diag_logs: list[tuple[int, str]]) -> None:
    log_meta_decision_trace(
        trigger="periodic",
        primary="hold",
        rationale="stage2_expectancy_failclosed",
        stall=True,
        coerced=True,
        source="apply_meta_plan",
    )
    lines = _records(diag_logs, "birth.meta.trace")
    assert len(lines) == 1
    assert lines[0][0] == logging.INFO


@pytest.mark.unit
def test_identity_survives_loading_data_progress_write(tmp_path: Path) -> None:
    write_birth_progress(
        tmp_path,
        stage="detected",
        phase="detected",
        message="boot",
        progress_pct=5.0,
        birth_start_time=1_700_000_000.0,
        birth_diag_contract=BIRTH_DIAG_CONTRACT,
        birth_code_fingerprint="abc123abc123abcd",
        birth_code_identity_ok=True,
        birth_code_identity_defects=[],
    )
    write_birth_progress(
        tmp_path,
        stage="loading_data",
        phase="loading_history",
        message="ticks",
        progress_pct=17.0,
        birth_start_time=1_700_000_000.0,
    )
    payload = json.loads(
        (tmp_path / "state" / "lumina_birth_progress.json").read_text(encoding="utf-8")
    )
    assert payload["birth_code_fingerprint"] == "abc123abc123abcd"
    assert payload["birth_code_identity_ok"] is True
    assert payload["birth_diag_contract"] == BIRTH_DIAG_CONTRACT


@pytest.mark.unit
def test_identity_progress_fields_for_boot_healthy() -> None:
    fields = identity_progress_fields_for_boot(reason="test")
    assert fields["birth_code_identity_ok"] is True
    assert fields["birth_diag_contract"] == BIRTH_DIAG_CONTRACT
    assert fields["birth_code_fingerprint"]


@pytest.mark.unit
def test_identity_progress_fields_for_boot_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*, reason: str = "startup") -> dict[str, Any]:
        raise RuntimeError("probe")

    monkeypatch.setattr(
        "lumina_core.birth.runtime_diagnostics.log_birth_code_fingerprint",
        _boom,
    )
    fields = identity_progress_fields_for_boot(reason="test")
    assert fields["birth_code_identity_ok"] is False
    assert fields["birth_diag_contract"] == "diag_error"
    assert "bootstrap_error:RuntimeError" in fields["birth_code_identity_defects"]
