"""S5 close_ledger archive: flush-before-wipe. Floors stay pinned. No new exam."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
from lumina_core.birth.s5_close_ledger_archive import (
    MEMORY_CAP,
    REQUIRED_ARCHIVE_KEYS,
    archive_line_count,
    flush_close_ledger_before_wipe,
    resolve_archive_path,
)
from lumina_core.birth.stage3_inband_ssot import (
    apply_s3_inband_rollout_metrics,
    persist_skill_settlement_fields,
    reset_skill_settlement_if_fresh_stage,
)


def _close_tr(**kw: object) -> dict[str, object]:
    row: dict[str, object] = {
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
    row.update(kw)
    return row


def _loop(tmp_path: Path, **kw: object) -> SimpleNamespace:
    host = SimpleNamespace(workspace_root=tmp_path)
    payload: dict[str, object] = {
        "host": host,
        "workspace_root": tmp_path,
        "close_ledger": [],
        "stage": SimpleNamespace(value="stage5_probe_handoff"),
        "s3_inband_explore": 0,
        "s3_inband_hold_tax_steps": 0,
        "s3_inband_idle_armed": False,
        "force_open_refractory_active": False,
        "occupancy_in_band_seen": False,
        "occ_floor_band_bars": 0,
        "occ_total_bars": 0,
        "stage_closes_stop_cum": 0,
        "stage_closes_target_cum": 0,
        "stage_closes_flatten_cum": 0,
        "stage_closes_time_stop_cum": 0,
        "stage_closes_unknown_cum": 0,
        "metrics_match_stage": False,
        "stage_trades": 0,
        "stage_policy_trades": 0,
        "stage_plant_trades": 0,
        "stage_policy_wins": 0,
        "stage_plant_wins": 0,
    }
    payload.update(kw)
    return SimpleNamespace(**payload)


def _rollout(n: int) -> SimpleNamespace:
    return SimpleNamespace(
        trajectories=[_close_tr() for _ in range(n)],
        s3_inband_explore=0,
        s3_inband_hold_tax_steps=0,
        s3_inband_idle_armed=False,
        force_open_refractory_active=False,
        occupancy_in_band_seen=False,
        occ_floor_band_bars=0,
        occ_total_bars=0,
    )


def test_a_floors_and_settlement_still_pinned() -> None:
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert S5_DD_EQUITY_USD == pytest.approx(50000)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert birth_gym_point_value() == pytest.approx(5.0)
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "S5_DD_EQUITY_USD = 50_000.0" in metrics
    assert "S5_EDGE_MIN = -0.03" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics


def test_b_flush_before_wipe_complete_and_reset(tmp_path: Path) -> None:
    loop = _loop(tmp_path)
    apply_s3_inband_rollout_metrics(loop, _rollout(10))
    archive = resolve_archive_path(tmp_path)
    assert archive_line_count(archive) == 10
    n = flush_close_ledger_before_wipe(loop, seal=True, clear_memory=True)
    assert n == 0
    assert archive_line_count(archive) == 10
    assert list(loop.close_ledger) == []
    assert (archive.with_name("s5_close_ledger.sha256")).is_file()

    leftover = _loop(tmp_path / "reset")
    leftover.close_ledger = [
        {
            "pnl": -1.0,
            "qty": 1,
            "point_value": 5.0,
            "close_reason": "stop",
            "gap": False,
            "regime": "NEUTRAL",
            "intended_risk_usd": 50.0,
            "trade_r": -0.02,
            "reward_on_close": -0.02,
            "cap_hit": False,
        }
        for _ in range(10)
    ]
    leftover._close_ledger_archived_n = 0
    leftover.metrics_match_stage = False
    leftover.stage_trades = 0
    reset_skill_settlement_if_fresh_stage(leftover)
    reset_archive = resolve_archive_path(tmp_path / "reset")
    assert archive_line_count(reset_archive) == 10
    assert list(leftover.close_ledger) == []


def test_c_cap_does_not_eat_the_archive(tmp_path: Path) -> None:
    loop = _loop(tmp_path)
    apply_s3_inband_rollout_metrics(loop, _rollout(2500))
    archive = resolve_archive_path(tmp_path)
    assert archive_line_count(archive) == 2500
    assert len(list(loop.close_ledger)) <= MEMORY_CAP
    assert len(list(loop.close_ledger)) == MEMORY_CAP
    payload = persist_skill_settlement_fields(loop)
    assert len(list(payload.get("close_ledger") or [])) <= MEMORY_CAP
    assert archive_line_count(archive) == 2500


def test_d_schema_has_required_keys(tmp_path: Path) -> None:
    loop = _loop(tmp_path)
    apply_s3_inband_rollout_metrics(
        loop,
        SimpleNamespace(
            trajectories=[
                _close_tr(ts_iso="2026-09-03T00:00:00Z", bar_index=17),
            ],
            s3_inband_explore=0,
            s3_inband_hold_tax_steps=0,
            s3_inband_idle_armed=False,
            force_open_refractory_active=False,
            occupancy_in_band_seen=False,
            occ_floor_band_bars=0,
            occ_total_bars=0,
        ),
    )
    archive = resolve_archive_path(tmp_path)
    lines = [
        json.loads(line)
        for line in archive.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    row = lines[0]
    for key in REQUIRED_ARCHIVE_KEYS:
        assert key in row, key
    assert row["stage"] == "stage5_probe_handoff"
    assert row["ts_iso"] == "2026-09-03T00:00:00Z"
    assert row["bar_index"] == 17
    assert row["qty"] == 1
    assert row["point_value"] == pytest.approx(5.0)


def test_e_live_hooks_wired_and_forbidden_krukken_absent() -> None:
    foundation = Path("lumina_core/birth/foundation_complete.py").read_text(encoding="utf-8")
    assert "flush_close_ledger_before_wipe" in foundation
    assert "clear_checkpoint(host.workspace_root)" in foundation
    assert foundation.index("flush_close_ledger_before_wipe") < foundation.index(
        "clear_checkpoint(host.workspace_root)"
    )
    ssot = Path("lumina_core/birth/stage3_inband_ssot.py").read_text(encoding="utf-8")
    assert "record_close_rows_from_trajectories" in ssot
    assert "flush_close_ledger_before_wipe" in ssot
    cert = Path("lumina_core/birth/certificate_evaluate.py").read_text(encoding="utf-8")
    assert "flush_close_ledger_before_wipe" in cert
    forbidden = (
        "S5_IDLE_REGIMES",
        "MAX_PLANT",
        "MAX_TIME_STOP",
        "if synthetic",
    )
    for rel in (
        "lumina_core/birth/s5_close_ledger_archive.py",
        "lumina_core/birth/stage3_inband_ssot.py",
        "lumina_core/birth/foundation_complete.py",
        "lumina_core/birth/foundation_metrics.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in src, f"{rel} contains {token}"


def test_cloud_workspace_writes_sibling_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "reports" / "birth_cloud_run" / "workspace"
    workspace.mkdir(parents=True)
    path = resolve_archive_path(workspace)
    assert path == tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "s5_close_ledger.jsonl"
    loop = _loop(workspace)
    apply_s3_inband_rollout_metrics(loop, _rollout(3))
    assert archive_line_count(path) == 3
    assert not (workspace / "reports").exists()
